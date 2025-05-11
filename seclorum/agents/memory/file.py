# seclorum/agents/memory/file.py
import logging
import os
import json
import time
import threading
from typing import Any
from seclorum.models import Task
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class FileBackend:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        logger.debug(f"Initialized FileBackend: log_path={self.log_path}")

    @contextmanager
    def _acquire_lock(self):
        logger.debug(f"Attempting to acquire file lock, thread={threading.current_thread().name}")
        self._lock.acquire()
        try:
            logger.debug("Acquired file lock")
            yield
        finally:
            self._lock.release()
            logger.debug("Released file lock")

    def save_conversation(self, prompt: str, response: str, task_id: str, agent_name: str) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        entry = {
            "task_id": task_id,
            "agent_name": agent_name,
            "prompt": prompt,
            "response": response,
            "timestamp": timestamp
        }
        with self._acquire_lock():
            try:
                log_data = []
                if os.path.exists(self.log_path):
                    with open(self.log_path, 'r') as f:
                        log_data = json.load(f)
                log_data.append(entry)
                with open(self.log_path, 'w') as f:
                    json.dump(log_data, f, indent=2)
                logger.debug(f"Saved conversation to log file: {self.log_path}")
            except Exception as e:
                logger.error(f"Failed to save to log file {self.log_path}: {str(e)}")
                raise

    def save_task(self, task: Task) -> None:
        prompt = task.description
        response = json.dumps(task.parameters)
        self.save_conversation(prompt, response, task.task_id, "system")
