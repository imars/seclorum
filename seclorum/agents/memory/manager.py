# seclorum/agents/memory/manager.py
from typing import List, Optional, Dict, Tuple
import logging
import os
import threading
import time
from datetime import datetime
from seclorum.models import Task
from seclorum.agents.memory.memory import Memory
from seclorum.agents.memory.vector import VectorBackend
import tempfile

logger = logging.getLogger(__name__)

class LockTimeoutError(RuntimeError):
    pass

class MemoryManager:
    _instances = {}

    def __init__(self, base_dir: str = "agents/logs/conversations", vector_db_path: Optional[str] = None, embedding_model: str = "nomic-embed-text:latest:ollama"):
        self.base_dir = base_dir
        self.vector_db_path = vector_db_path or os.path.join(tempfile.gettempdir(), "chroma_db")
        self.embedding_model = embedding_model
        os.makedirs(self.base_dir, exist_ok=True)
        os.environ["CHROMA_TELEMETRY_ENABLED"] = "false"  # Disable telemetry
        self.memories = {}
        self.vector_backend = VectorBackend(self.vector_db_path)
        self._lock = threading.Lock()
        self._memory_lock = threading.Lock()
        logger.debug(f"Initialized MemoryManager: base_dir={self.base_dir}, vector_db_path={self.vector_db_path}, embedding_model={self.embedding_model}")

    def get_memory(self, session_id: str, preserve_db: bool = False) -> Memory:
        with self._memory_lock:
            if session_id not in self.memories:
                db_path = os.path.join(tempfile.gettempdir(), f"memory_{session_id}.db")
                log_path = os.path.join(self.base_dir, f"conversation_{session_id}.json")
                self.memories[session_id] = Memory(
                    session_id, db_path, log_path, self.vector_backend, self.embedding_model, preserve_db
                )
                logger.debug(f"Created new Memory instance for session_id={session_id}, thread={threading.current_thread().name}")
            else:
                logger.debug(f"Reusing existing Memory instance for session_id={session_id}, thread={threading.current_thread().name}")
        return self.memories[session_id]

    def save(self, prompt: str, response: str, task_id: str, agent_name: str, session_id: str) -> None:
        memory = self.get_memory(session_id)
        memory.save(prompt, response, task_id, agent_name)
        logger.debug(f"Saved conversation via Memory: session_id={session_id}, task_id={task_id}")

    def load_history(self, task_id: str, agent_name: str, session_id: str) -> List[Tuple[str, str, str]]:
        memory = self.get_memory(session_id)
        return memory.load_conversation_history(task_id, agent_name)

    def format_history(self, task_id: str, agent_name: str, session_id: str) -> str:
        memory = self.get_memory(session_id)
        history = self.load_history(task_id, agent_name, session_id)
        return memory.format_history(history)

    def find_similar(self, query: str, task_id: Optional[str] = None, n_results: int = 3) -> List[Dict]:
        memory = self.get_memory(self.memories.keys().__iter__().__next__())  # Use first session_id
        results = memory.find_similar(query, task_id, n_results)
        logger.debug(f"Found {len(results)} similar items for query: {query[:50]}...")
        return results

    def cache_response(self, prompt_hash: str, response: str, session_id: str) -> None:
        memory = self.get_memory(session_id)
        memory.cache_response(prompt_hash, response)

    def load_cached_response(self, prompt_hash: str, session_id: str) -> Optional[str]:
        memory = self.get_memory(session_id)
        return memory.load_cached_response(prompt_hash)

    def save_task(self, task: Task, session_id: str) -> None:
        memory = self.get_memory(session_id)
        memory.save_task(task)

    def load_task(self, task_id: str, session_id: str) -> Optional[Task]:
        memory = self.get_memory(session_id)
        return memory.load_task(task_id)

    def stop(self):
        for memory in self.memories.values():
            memory.stop()
        self.vector_backend.stop()
        self.memories.clear()
        logger.debug("Stopped MemoryManager")
