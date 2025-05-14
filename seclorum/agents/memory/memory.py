# seclorum/agents/memory/memory.py
import os
import logging
import json
from typing import List, Optional, Tuple, Dict
from seclorum.models import Task
from seclorum.agents.memory.sqlite import SQLiteBackend
from seclorum.agents.memory.file import FileBackend
from seclorum.agents.memory.vector import VectorBackend

logger = logging.getLogger(__name__)

class Memory:
    def __init__(
        self,
        session_id: str,
        sqlite_db_path: str = "memory.db",
        log_path: str = "conversation_log.json",
        vector_backend: Optional[VectorBackend] = None,
        embedding_model: str = None,
    ):
        self.session_id = session_id
        self.sqlite_db_path = sqlite_db_path
        self.log_path = log_path
        self.vector_backend = vector_backend
        self.embedding_model = embedding_model
        os.makedirs(os.path.dirname(self.sqlite_db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        self.sqlite_backend = SQLiteBackend(self.sqlite_db_path)
        self.file_backend = FileBackend(self.log_path)
        self._initialize()

    def _initialize(self):
        """Initialize memory backends."""
        try:
            self.sqlite_backend.initialize()
            logger.info(f"Initialized SQLiteBackend at {self.sqlite_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLiteBackend: {str(e)}")
            raise
        try:
            self.file_backend.initialize()
            logger.info(f"Initialized FileBackend at {self.log_path}")
        except Exception as e:
            logger.error(f"Failed to initialize FileBackend: {str(e)}")
            raise
        if self.vector_backend:
            try:
                self.vector_backend.initialize(self.embedding_model)
                logger.info(f"Initialized VectorBackend with model {self.embedding_model}")
            except Exception as e:
                logger.error(f"Failed to initialize VectorBackend: {str(e)}")
                raise

    def save(self, prompt: str, response: str, task_id: str, agent_name: str) -> None:
        """Save a conversation to all backends."""
        try:
            self.sqlite_backend.save_conversation(
                session_id=self.session_id,
                task_id=task_id,
                agent_name=agent_name,
                prompt=prompt,
                response=response,
            )
            logger.debug(f"Saved conversation to SQLite: session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}")
        except Exception as e:
            logger.warning(f"Failed to save to SQLiteBackend: {str(e)}")
        try:
            self.file_backend.save_conversation(
                session_id=self.session_id,
                task_id=task_id,
                agent_name=agent_name,
                prompt=prompt,
                response=response,
            )
            logger.debug(f"Saved conversation to FileBackend: session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}")
        except Exception as e:
            logger.warning(f"Failed to save to FileBackend: {str(e)}")
        if self.vector_backend:
            try:
                text = f"{prompt}\n{response}"
                self.vector_backend.add_embedding(
                    text=text,
                    session_id=self.session_id,
                    task_id=task_id,
                    agent_name=agent_name,
                )
                logger.debug(f"Saved embedding to VectorBackend: session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}")
            except Exception as e:
                logger.warning(f"Failed to save to VectorBackend: {str(e)}")

    def load_history(self, task_id: str, agent_name: str) -> List[Tuple[str, str, str]]:
        """Load conversation history for the task and agent."""
        try:
            history = self.sqlite_backend.load_conversation_history(
                session_id=self.session_id,
                task_id=task_id,
                agent_name=agent_name,
            )
            logger.debug(f"Loaded conversation history from SQLite: session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}, count={len(history)}")
            return history
        except Exception as e:
            logger.warning(f"Failed to load conversation history from SQLiteBackend: {str(e)}")
            return []

    def load_cached_response(self, prompt_hash: str) -> Optional[str]:
        """Load a cached response for the prompt hash."""
        try:
            response = self.sqlite_backend.load_cached_response(
                session_id=self.session_id,
                prompt_hash=prompt_hash,
            )
            if response:
                logger.debug(f"Loaded cached response from SQLite: session_id={self.session_id}, prompt_hash={prompt_hash}")
            return response
        except Exception as e:
            logger.warning(f"Failed to load cached response from SQLiteBackend: {str(e)}")
            return None

    def cache_response(self, prompt_hash: str, response: str) -> None:
        """Cache a response for the prompt hash."""
        try:
            self.sqlite_backend.cache_response(
                session_id=self.session_id,
                prompt_hash=prompt_hash,
                response=response,
            )
            logger.debug(f"Cached response in SQLite: session_id={self.session_id}, prompt_hash={prompt_hash}")
        except Exception as e:
            logger.warning(f"Failed to cache response in SQLiteBackend: {str(e)}")

    def save_task(self, task: Task) -> None:
        """Save a task to the SQLite backend."""
        try:
            self.sqlite_backend.save_task(
                session_id=self.session_id,
                task_id=task.task_id,
                task_data=task.dict(),
            )
            logger.debug(f"Saved task to SQLite: session_id={self.session_id}, task_id={task.task_id}")
        except Exception as e:
            logger.warning(f"Failed to save task to SQLiteBackend: {str(e)}")

    def load_task(self, task_id: str) -> Optional[Task]:
        """Load a task from the SQLite backend."""
        try:
            task_data = self.sqlite_backend.load_task(
                session_id=self.session_id,
                task_id=task_id,
            )
            if task_data:
                logger.debug(f"Loaded task from SQLite: session_id={self.session_id}, task_id={task_id}")
                return Task(**task_data)
            return None
        except Exception as e:
            logger.warning(f"Failed to load task from SQLiteBackend: {str(e)}")
            return None

    def find_similar(self, text: str, task_id: str, n_results: int = 5) -> List[Dict]:
        """Find similar conversations using the vector backend."""
        if not self.vector_backend:
            logger.warning("VectorBackend not initialized, cannot find similar conversations")
            return []
        try:
            results = self.vector_backend.find_similar(
                text=text,
                session_id=self.session_id,
                task_id=task_id,
                n_results=n_results,
            )
            logger.debug(f"Found {len(results)} similar conversations for task_id={task_id}")
            return results
        except Exception as e:
            logger.warning(f"Failed to find similar conversations in VectorBackend: {str(e)}")
            return []

    def stop(self):
        """Signal shutdown of memory backends."""
        try:
            self.sqlite_backend.stop()
            logger.info("Stopped SQLiteBackend")
        except Exception as e:
            logger.warning(f"Failed to stop SQLiteBackend: {str(e)}")
        try:
            self.file_backend.stop()
            logger.info("Stopped FileBackend")
        except Exception as e:
            logger.warning(f"Failed to stop FileBackend: {str(e)}")
        if self.vector_backend:
            try:
                self.vector_backend.stop()
                logger.info("Stopped VectorBackend")
            except Exception as e:
                logger.warning(f"Failed to stop VectorBackend: {str(e)}")

    def close(self):
        """Close all backend resources."""
        try:
            self.sqlite_backend.close()
            logger.info("Closed SQLiteBackend")
        except Exception as e:
            logger.warning(f"Failed to close SQLiteBackend: {str(e)}")
        try:
            self.file_backend.close()
            logger.info("Closed FileBackend")
        except Exception as e:
            logger.warning(f"Failed to close FileBackend: {str(e)}")
        if self.vector_backend:
            try:
                self.vector_backend.close()
                logger.info("Closed VectorBackend")
            except Exception as e:
                logger.warning(f"Failed to close VectorBackend: {str(e)}")
