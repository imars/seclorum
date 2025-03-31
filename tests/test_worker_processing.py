# tests/test_worker_processing.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum") or "redis" in module:
        sys.modules.pop(module)

import os
import time
import redis
import logging
from unittest.mock import patch, Mock
from seclorum.agents.worker import Worker

os.environ["TOKENIZERS_PARALLELISM"] = "false"

def test_worker_processing():
    # Logger setup inside function to apply after imports
    logger = logging.getLogger("Seclorum")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.handlers = [handler]
    logger.propagate = False

    worker_logger = logging.getLogger("Worker")
    worker_logger.setLevel(logging.DEBUG)
    worker_logger.handlers = [handler]  # Same handler as Seclorum
    worker_logger.propagate = False

    session_id = "test_worker_session"
    task_id = "test1"
    description = "Test task description"
    source = "UnitTest"

    log_dir = "logs/conversations"
    os.makedirs(log_dir, exist_ok=True)
    sqlite_file = os.path.join(log_dir, f"conversations_{session_id}.db")
    print(f"Expected SQLite file: {os.path.abspath(sqlite_file)}")

    import sqlite3
    with sqlite3.connect(sqlite_file) as conn:
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
    print(f"Manual SQLite test file exists: {os.path.exists(sqlite_file)}")
    os.remove(sqlite_file)

    # Test 1: Successful processing with Redis mocked
    with patch("seclorum.agents.redis_mixin.RedisMixin.connect_redis") as mock_connect, \
         patch("logging.Logger.info") as mock_info:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.set.return_value = None
        mock_connect.return_value = None
        worker = Worker(task_id, description, source, session_id)
        worker.redis_client = mock_client
        worker.redis_available = True
        print(f"Redis available after init in Test 1: {worker.redis_available}")
        print(f"Mock connect called in Test 1: {mock_connect.called}")

        status, result = worker.process_task(task_id, description)
        assert status == "completed"
        assert result == f"Processed task: {description}"
        print(f"Checking if SQLite file exists after processing in Test 1: {os.path.exists(sqlite_file)}")
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created"

        worker.stop()

    # Test 2: Successful processing without Redis
    os.remove(sqlite_file)
    with patch("seclorum.agents.redis_mixin.redis.Redis") as mock_redis:
        mock_redis.side_effect = redis.ConnectionError("Mock Redis failure")
        print(f"Mock Redis setup for Test 2: {mock_redis}")
        worker = Worker(task_id, description, source, session_id)
        print(f"Redis available after init in Test 2: {worker.redis_available}")
        print(f"Mock Redis called in Test 2: {mock_redis.called}")
        assert not worker.redis_available, "Redis should be unavailable"

        status, result = worker.process_task(task_id, description)
        assert status == "completed"
        assert result == f"Processed task: {description}"
        print(f"Checking if SQLite file exists after processing in Test 2: {os.path.exists(sqlite_file)}")
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created after no Redis"

        worker.stop()

    # Test 3: Error during processing
    os.remove(sqlite_file)
    with patch("seclorum.agents.redis_mixin.RedisMixin.connect_redis") as mock_connect, \
         patch("logging.Logger.info") as mock_info:
        mock_client = Mock()
        mock_client.ping.return_value = True
        mock_client.set.return_value = None
        mock_connect.return_value = None
        worker = Worker(task_id, description, source, session_id)
        worker.redis_client = mock_client
        worker.redis_available = True
        print(f"Redis available after init in Test 3: {worker.redis_available}")
        print(f"Mock connect called in Test 3: {mock_connect.called}")

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = Exception("Simulated processing error")
            status, result = worker.process_task(task_id, description)
            assert status == "failed"
            assert "Simulated processing error" in result
            print(f"Checking if SQLite file exists after processing in Test 3: {os.path.exists(sqlite_file)}")
            assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created after error"

        worker.stop()

    # Cleanup
    if os.path.exists(sqlite_file):
        os.remove(sqlite_file)
    if os.path.exists(log_dir) and not os.listdir(log_dir):
        os.rmdir(log_dir)

if __name__ == "__main__":
    test_worker_processing()
    print("Worker processing tests passed!")
