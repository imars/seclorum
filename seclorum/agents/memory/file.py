# seclorum/agents/memory/file.py
import logging
import os
import json
import time
import threading
from typing import List, Optional, Tuple, Dict
from seclorum.models import Task
from seclorum.agents.memory.protocol import MemoryBackend
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FileBackend(MemoryBackend):
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._lock = threading.Lock()

    def initialize(self, **kwargs) -> None:
        """Initialize the file backend by ensuring the log file directory exists."""
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            # Ensure the log file exists with the correct structure
            if not os.path.exists(self.log_path):
                with self._acquire_lock():
                    with open(self.log_path, 'w') as f:
                        json.dump({"conversations": [], "tasks": []}, f, indent=2)
            logger.info(f"Initialized FileBackend: log_path={self.log_path}")
        except Exception as e:
            logger.error(f"Failed to initialize FileBackend: {str(e)}")
            raise

    @contextmanager
    def _acquire_lock(self):
        """Acquire the file lock for thread-safe operations."""
        logger.debug(f"Attempting to acquire file lock, thread={threading.current_thread().name}")
        self._lock.acquire()
        try:
            logger.debug("Acquired file lock")
            yield
        finally:
            self._lock.release()
            logger.debug("Released file lock")

    def _read_log(self) -> Dict:
        """Read the entire log file, returning an empty structure if it doesn't exist."""
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, 'r') as f:
                    return json.load(f)
            return {"conversations": [], "tasks": []}
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to read log file {self.log_path}: {str(e)}")
            return {"conversations": [], "tasks": []}

    def _write_log(self, log_data: Dict) -> None:
        """Write the log data to the file."""
        try:
            with open(self.log_path, 'w') as f:
                json.dump(log_data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to write to log file {self.log_path}: {str(e)}")
            raise

    def save_conversation(
        self, session_id: str, task_id: str, agent_name: str, prompt: str, response: str
    ) -> None:
        """Save a conversation to the conversations list in the log file."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        entry = {
            "session_id": session_id,
            "task_id": task_id,
            "agent_name": agent_name,
            "prompt": prompt,
            "response": response,
            "timestamp": timestamp
        }
        with self._acquire_lock():
            try:
                log_data = self._read_log()
                log_data["conversations"].append(entry)
                self._write_log(log_data)
                logger.debug(
                    f"Saved conversation to log file: session_id={session_id}, "
                    f"task_id={task_id}, agent_name={agent_name}, log_path={self.log_path}"
                )
            except Exception as e:
                logger.error(f"Failed to save conversation to log file {self.log_path}: {str(e)}")
                raise

    def load_conversation_history(
        self, session_id: str, task_id: str, agent_name: str
    ) -> List[Tuple[str, str, str]]:
        """Load conversation history for the given session, task, and agent."""
        with self._acquire_lock():
            try:
                log_data = self._read_log()
                history = [
                    (entry["prompt"], entry["response"], entry["timestamp"])
                    for entry in log_data["conversations"]
                    if entry["session_id"] == session_id
                    and entry["task_id"] == task_id
                    and entry["agent_name"] == agent_name
                ]
                logger.debug(
                    f"Loaded {len(history)} conversation records: session_id={session_id}, "
                    f"task_id={task_id}, agent_name={agent_name}, log_path={self.log_path}"
                )
                return sorted(history, key=lambda x: x[2])  # Sort by timestamp
            except Exception as e:
                logger.error(f"Failed to load conversation history from {self.log_path}: {str(e)}")
                return []

    def cache_response(self, session_id: str, prompt_hash: str, response: str) -> None:
        """Cache a response (not natively supported, log warning)."""
        logger.warning("FileBackend does not support caching responses")

    def load_cached_response(self, session_id: str, prompt_hash: str) -> Optional[str]:
        """Load a cached response (not natively supported, return None)."""
        logger.warning("FileBackend does not support loading cached responses")
        return None

    def save_task(self, session_id: str, task_id: str, task_data: Dict) -> None:
        """Save task data to the tasks list in the log file."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        entry = {
            "session_id": session_id,
            "task_id": task_id,
            "task_data": task_data,
            "timestamp": timestamp
        }
        with self._acquire_lock():
            try:
                log_data = self._read_log()
                # Remove any existing task with the same session_id and task_id
                log_data["tasks"] = [
                    t for t in log_data["tasks"]
                    if not (t["session_id"] == session_id and t["task_id"] == task_id)
                ]
                log_data["tasks"].append(entry)
                self._write_log(log_data)
                logger.debug(
                    f"Saved task to log file: session_id={session_id}, task_id={task_id}, log_path={self.log_path}"
                )
            except Exception as e:
                logger.error(f"Failed to save task to log file {self.log_path}: {str(e)}")
                raise

    def load_task(self, session_id: str, task_id: str) -> Optional[Dict]:
        """Load the latest task data for the given session and task ID."""
        with self._acquire_lock():
            try:
                log_data = self._read_log()
                tasks = [
                    t for t in log_data["tasks"]
                    if t["session_id"] == session_id and t["task_id"] == task_id
                ]
                if tasks:
                    # Return the most recent task (latest timestamp)
                    latest_task = max(tasks, key=lambda x: x["timestamp"])
                    logger.debug(
                        f"Loaded task: session_id={session_id}, task_id={task_id}, log_path={self.log_path}"
                    )
                    return latest_task["task_data"]
                return None
            except Exception as e:
                logger.error(f"Failed to load task from {self.log_path}: {str(e)}")
                return None

    def find_similar(
        self, text: str, session_id: str, task_id: str, n_results: int
    ) -> List[Dict]:
        """Find similar conversations (not natively supported, return empty list)."""
        logger.warning("FileBackend does not support similarity search")
        return []

    def stop(self) -> None:
        """Signal shutdown of the FileBackend."""
        logger.info(f"Signaled shutdown for FileBackend: log_path={self.log_path}")

    def close(self) -> None:
        """Close the FileBackend (no-op, as no resources need closing)."""
        logger.info(f"Closed FileBackend: log_path={self.log_path}")
