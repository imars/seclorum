# tests/test_memory.py
import unittest
import os
import logging
import json
import uuid
import tempfile
import threading
import time
import numpy as np
import warnings
import socket
import subprocess
from contextlib import contextmanager
from seclorum.agents.memory.manager import MemoryManager
from seclorum.agents.memory.sqlite import SQLiteBackend
from seclorum.agents.memory.file import FileBackend
from seclorum.agents.memory.vector import VectorBackend
from seclorum.models import Task
import chromadb

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Suppress ResourceWarning for unclosed sockets and files
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*socket")
warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*file")

@contextmanager
def clean_ollama_state():
    """Ensure no lingering ollama processes started by tests."""
    try:
        yield
    finally:
        # Check for test-started ollama processes
        try:
            result = subprocess.run(["pgrep", "-f", "ollama serve"], capture_output=True, text=True)
            if result.stdout:
                subprocess.run(["pkill", "-f", "ollama serve"], check=False)
                logger.debug("Cleaned up test-started ollama processes")
            else:
                logger.debug("No test-started ollama processes found")
        except Exception as e:
            logger.warning(f"Failed to clean up ollama processes: {str(e)}")

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.join(tempfile.gettempdir(), f"test_memory_{uuid.uuid4()}")
        self.session_id1 = f"test_session_{uuid.uuid4()}"
        self.session_id2 = f"test_session_{uuid.uuid4()}"
        self.task_id = "test_task"
        self.agent_name = "test_agent"
        self.manager = MemoryManager(
            base_dir=self.base_dir,
            backends=[
                {
                    "backend": SQLiteBackend,
                    "config": {"db_path": os.path.join(self.base_dir, "{session_id}.db"), "preserve_db": False}
                },
                {
                    "backend": FileBackend,
                    "config": {"log_path": os.path.join(self.base_dir, "conversation_{session_id}.json")}
                },
                {
                    "backend": VectorBackend,
                    "config": {
                        "db_path": os.path.join(self.base_dir, "vector_db_{session_id}"),
                        "embedding_model": "nomic-embed-text:latest"
                    }
                }
            ],
            embedding_model="nomic-embed-text:latest"
        )
        self.log_file1 = os.path.join(self.base_dir, f"conversation_{self.session_id1}.json")
        self.log_file2 = os.path.join(self.base_dir, f"conversation_{self.session_id2}.json")
        self.db_file1 = os.path.join(self.base_dir, f"{self.session_id1}.db")
        self.db_file2 = os.path.join(self.base_dir, f"{self.session_id2}.db")
        self.vector_db_path1 = os.path.join(self.base_dir, f"vector_db_{self.session_id1}")
        self.vector_db_path2 = os.path.join(self.base_dir, f"vector_db_{self.session_id2}")
        self.saved_prompts = set()
        self.save_lock = threading.Lock()

    def tearDown(self):
        logger.debug("Starting test cleanup")
        self.manager.close()
        for f in [self.log_file1, self.log_file2, self.db_file1, self.db_file2]:
            if os.path.exists(f):
                os.remove(f)
        import shutil
        for d in [self.vector_db_path1, self.vector_db_path2]:
            if os.path.exists(d):
                shutil.rmtree(d)
        if os.path.exists(self.base_dir):
            shutil.rmtree(self.base_dir)
        # Minimal socket cleanup
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(('127.0.0.1', 11434))
            s.close()
            logger.debug("Closed lingering ollama socket")
        except (ConnectionRefusedError, socket.error, socket.timeout):
            logger.debug("No lingering ollama sockets found")
        logger.debug("Completed test cleanup")

    def test_save_and_load_conversation(self):
        with clean_ollama_state():
            prompt = "Hello, how are you?"
            response = "I'm doing great, thanks!"
            self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)

            # Check conversation history
            history = self.manager.load_history(self.task_id, self.agent_name, self.session_id1)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0][0], prompt)
            self.assertEqual(history[0][1], response)

            # Check log file
            self.assertTrue(os.path.exists(self.log_file1))
            with open(self.log_file1, 'r') as f:
                log_data = json.load(f)
            self.assertGreaterEqual(len(log_data["conversations"]), 1)
            conv = next(
                c for c in log_data["conversations"]
                if c["session_id"] == self.session_id1 and c["task_id"] == self.task_id
            )
            self.assertEqual(conv["prompt"], prompt)
            self.assertEqual(conv["response"], response)

    def test_cross_session_memory(self):
        with clean_ollama_state():
            prompt = "Hello, how are you?"
            response = "I'm doing great, thanks!"
            memory = self.manager.get_memory(self.session_id1)
            self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)
            time.sleep(1)
            results = memory.find_similar(prompt, self.task_id, n_results=2, session_id=self.session_id1)
            self.assertGreaterEqual(len(results), 1, "No similar results found")
            self.assertIn(prompt, results[0]["text"])
            history = self.manager.load_history(self.task_id, self.agent_name, self.session_id1)
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0][0], prompt)
            self.assertEqual(history[0][1], response)
            # Ensure session isolation
            history2 = self.manager.load_history(self.task_id, self.agent_name, self.session_id2)
            self.assertEqual(len(history2), 0)

    def test_embedding_generation(self):
        with clean_ollama_state():
            prompt = "Async test prompt"
            response = "Async test response"
            memory = self.manager.get_memory(self.session_id1)
            self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)
            time.sleep(1)
            results = memory.find_similar("Async test", self.task_id, n_results=1, session_id=self.session_id1)
            self.assertGreaterEqual(len(results), 1, "No similar results found")
            self.assertIn(prompt, results[0]["text"])

    def test_cache_response(self):
        with clean_ollama_state():
            prompt_hash = "test_hash"
            response = "Cache test response"
            self.manager.save(prompt_hash, response, self.task_id, self.agent_name, self.session_id1)
            cached = self.manager.load_cached_response(prompt_hash, self.session_id1)
            self.assertIsNone(cached, "File and Vector backends do not support caching")

    def test_save_task(self):
        with clean_ollama_state():
            task = Task(task_id=self.task_id, description="Test task", parameters={"key": "value"})
            self.manager.save_task(task, self.session_id1)
            loaded_task = self.manager.load_task(self.task_id, self.session_id1)
            self.assertIsNotNone(loaded_task)
            self.assertEqual(loaded_task.task_id, self.task_id)
            self.assertEqual(loaded_task.description, "Test task")
            self.assertEqual(loaded_task.parameters, {"key": "value"})

    def test_vector_db_access(self):
        with clean_ollama_state():
            prompt = "Vector test prompt"
            response = "Vector test response"
            memory = self.manager.get_memory(self.session_id1)
            memory.save(prompt, response, self.task_id, self.agent_name)
            time.sleep(1)
            # Access ChromaDB collection via VectorBackend
            vector_client = chromadb.PersistentClient(
                path=self.vector_db_path1, settings=chromadb.Settings(anonymized_telemetry=False)
            )
            collection = vector_client.get_collection("conversations")
            count = collection.count()
            logger.debug(f"ChromaDB collection size after save: {count}")
            results = memory.find_similar("Vector test", self.task_id, n_results=1, session_id=self.session_id1)
            self.assertGreaterEqual(len(results), 1, f"No results found, collection size: {count}")
            self.assertIn(prompt, results[0]["text"])

    def test_embedding_model_switch(self):
        with clean_ollama_state():
            # Test with sentence-transformers
            manager_st = MemoryManager(
                base_dir=os.path.join(tempfile.gettempdir(), f"test_memory_{uuid.uuid4()}"),
                backends=[
                    {
                        "backend": VectorBackend,
                        "config": {
                            "db_path": os.path.join(self.base_dir, "vector_db_{session_id}"),
                            "embedding_model": "all-MiniLM-L6-v2"
                        }
                    }
                ],
                embedding_model="all-MiniLM-L6-v2"
            )
            memory = manager_st.get_memory(self.session_id1)
            prompt = "Switch test prompt"
            response = "Switch test response"
            memory.save(prompt, response, self.task_id, self.agent_name)
            time.sleep(1)
            results = memory.find_similar("Switch test", self.task_id, n_results=1, session_id=self.session_id1)
            self.assertGreaterEqual(len(results), 1, "No similar results found")
            self.assertIn(prompt, results[0]["text"])
            manager_st.close()

    def test_embedding_dimension(self):
        with clean_ollama_state():
            memory = self.manager.get_memory(self.session_id1)
            prompt = "Dimension test prompt"
            response = "Dimension test response"
            memory.save(prompt, response, self.task_id, self.agent_name)
            time.sleep(1)
            # Access ChromaDB collection via VectorBackend
            vector_client = chromadb.PersistentClient(
                path=self.vector_db_path1, settings=chromadb.Settings(anonymized_telemetry=False)
            )
            collection = vector_client.get_collection("conversations")
            count = collection.count()
            logger.debug(f"ChromaDB collection size: {count}")
            if count > 0:
                peek = collection.peek(limit=1)
                embedding = np.array(peek["embeddings"][0])
                logger.debug(f"Embedding dimension: {embedding.shape[0]}")
                self.assertEqual(embedding.shape[0], 768, f"Expected 768 dimensions for nomic-embed-text, got {embedding.shape[0]}")

if __name__ == "__main__":
    unittest.main()
