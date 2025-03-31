# tests/test_worker_processing.py
import os
import time
import redis
import logging
from unittest.mock import patch
from seclorum.agents.worker import Worker

# Suppress tokenizers parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Configure logging for debug output
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_worker_processing():
    # Test setup
    session_id = "test_worker_session"
    task_id = "test1"
    description = "Test task description"
    source = "UnitTest"

    log_dir = "logs/conversations"
    os.makedirs(log_dir, exist_ok=True)
    sqlite_file = os.path.join(log_dir, f"conversations_{session_id}.db")
    print(f"Expected SQLite file: {os.path.abspath(sqlite_file)}")

    # Test 1: Successful processing with Redis
    with patch("redis.Redis") as mock_redis:
        mock_client = mock_redis.return_value
        mock_client.ping.return_value = True
        worker = Worker(task_id, description, source, session_id)
        assert worker.redis_available, "Redis should be available with mock"

        status, result = worker.process_task(task_id, description)
        assert status == "completed"
        assert result == f"Processed task: {description}"
        print(f"Checking if SQLite file exists after processing: {os.path.exists(sqlite_file)}")
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created"

        worker.stop()

    # Test 2: Successful processing without Redis
    with patch("redis.Redis") as mock_redis:
        mock_redis.side_effect = redis.ConnectionError("Mock Redis failure")
        worker = Worker(task_id, description, source, session_id)
        assert not worker.redis_available, "Redis should be unavailable"

        status, result = worker.process_task(task_id, description)
        assert status == "completed"
        assert result == f"Processed task: {description}"
        assert os.path.exists(sqlite_file), f"SQLite file {sqlite_file} not created after no Redis"

        worker.stop()

    # Test 3: Error during processing
    with patch("redis.Redis") as mock_redis:
        mock_client = mock_redis.return_value
        mock_client.ping.return_value = True
        worker = Worker(task_id, description, source, session_id)

        with patch("time.sleep") as mock_sleep:
            mock_sleep.side_effect = Exception("Simulated processing error")
            status, result = worker.process_task(task_id, description)
            assert status == "failed"
            assert "Simulated processing error" in result
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
