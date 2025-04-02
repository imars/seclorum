# tests/test_worker_code_validation.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum") or "redis" in module:
        sys.modules.pop(module)

import os
import redis
import logging
import chromadb
from datetime import datetime
from unittest.mock import patch, Mock
from seclorum.agents.worker import Worker

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def test_worker_code_validation():
    logger = logging.getLogger("Seclorum")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.handlers = [handler]
    logger.propagate = False

    worker_logger = logging.getLogger("Worker")
    worker_logger.setLevel(logging.DEBUG)
    worker_logger.handlers = [handler]
    worker_logger.propagate = False

    session_id = f"test_validation_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    task_id = "val1"
    description = "create a Python script to list all Python files in a directory"
    source = "UnitTest"
    model = "llama3.2:1b"

    log_dir = "logs/conversations"
    os.makedirs(log_dir, exist_ok=True)
    sqlite_file = os.path.join(log_dir, f"conversations_{session_id}.db")
    print(f"Expected SQLite file: {os.path.abspath(sqlite_file)}")

    # Reset ChromaDB
    chroma_client = chromadb.PersistentClient(
        path=os.path.join(log_dir, "chroma_shared"),
        settings=chromadb.Settings(allow_reset=True)
    )
    chroma_client.reset()
    print("ChromaDB reset complete")

    # Test 1: Successful code execution with Redis
    with patch("seclorum.agents.redis_mixin.RedisMixin.connect_redis") as mock_connect, \
         patch("logging.Logger.info") as mock_info, \
         patch("ollama.generate") as mock_ollama:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.set.return_value = None
        mock_connect.return_value = None
        mock_ollama.return_value = {
            "response": "import os\n\nfiles = [f for f in os.listdir('.') if f.endswith('.py')]\nfor file in files:\n    print(file)"
        }
        worker = Worker(task_id, description, source, session_id, model=model)
        worker.redis_client = mock_client
        worker.redis_available = True
        print(f"Redis available after init in Test 1: {worker.redis_available}")
        print(f"Mock connect called in Test 1: {mock_connect.called}")

        status, result = worker.process_task(task_id, description, execute_code=True)
        assert status == "completed"
        assert "import os" in result
        assert "Output:" in result
        assert ".py" in result  # Expect some file names in output
        print(f"Execution result in Test 1: {result}")
        print(f"Checking if SQLite file exists after processing in Test 1: {os.path.exists(sqlite_file)}")
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created"

        worker.memory.process_embedding_queue()
        history = worker.memory.load_conversation_history(task_id=task_id)
        print(f"Raw conversation history in Test 1: {history}")
        assert f"Task {task_id}: {description}" in history, "Prompt not in history"
        assert "Code executed successfully" in history, "Execution result not in history"

        chroma_contents = worker.memory.collection.get()
        assert len(chroma_contents["ids"]) > 0, "No embeddings in ChromaDB"
        assert any("Code executed successfully" in doc for doc in chroma_contents["documents"]), "Result not embedded in ChromaDB"
        print(f"ChromaDB contents in Test 1: {chroma_contents['documents']}")

        worker.stop()

    # Test 2: Code execution with syntax error
    os.remove(sqlite_file)
    with patch("seclorum.agents.redis_mixin.RedisMixin.connect_redis") as mock_connect, \
         patch("logging.Logger.info") as mock_info, \
         patch("ollama.generate") as mock_ollama:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.set.return_value = None
        mock_connect.return_value = None
        mock_ollama.return_value = {
            "response": "import os\n\nfiles = [f for f in os.listdir('.') if f.endswith('.py')\nfor file in files:\n    print(file)"  # Missing closing bracket
        }
        worker = Worker(task_id, description, source, session_id, model=model)
        worker.redis_client = mock_client
        worker.redis_available = True
        print(f"Redis available after init in Test 2: {worker.redis_available}")
        print(f"Mock connect called in Test 2: {mock_connect.called}")

        status, result = worker.process_task(task_id, description, execute_code=True)
        assert status == "completed"  # Still "completed" as generation succeeded
        assert "Code execution failed" in result
        assert "SyntaxError" in result
        print(f"Execution result in Test 2: {result}")
        print(f"Checking if SQLite file exists after processing in Test 2: {os.path.exists(sqlite_file)}")
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created"

        worker.memory.process_embedding_queue()
        history = worker.memory.load_conversation_history(task_id=task_id)
        print(f"Raw conversation history in Test 2: {history}")
        assert f"Task {task_id}: {description}" in history, "Prompt not in history"
        assert "Code execution failed" in history, "Error not in history"

        chroma_contents = worker.memory.collection.get()
        assert len(chroma_contents["ids"]) > 0, "No embeddings in ChromaDB"
        assert any("Code execution failed" in doc for doc in chroma_contents["documents"]), "Error not embedded in ChromaDB"
        print(f"ChromaDB contents in Test 2: {chroma_contents['documents']}")

        worker.stop()

    # Cleanup
    if os.path.exists(sqlite_file):
        os.remove(sqlite_file)
    if os.path.exists(log_dir) and not os.listdir(log_dir):
        os.rmdir(log_dir)

if __name__ == "__main__":
    test_worker_code_validation()
    print("Worker code validation tests passed!")
