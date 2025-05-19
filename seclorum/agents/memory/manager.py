# seclorum/agents/memory/manager.py
import os
import logging
import subprocess
import atexit
import time
import socket
from typing import List, Dict, Optional, Tuple
from seclorum.models import Task
from seclorum.agents.memory.memory import Memory
from seclorum.agents.memory.sqlite import SQLiteBackend
from seclorum.agents.memory.file import FileBackend
from seclorum.agents.memory.vector import VectorBackend
import ollama

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(
        self,
        base_dir: str = "agents/logs/conversations",
        backends: Optional[List[Dict[str, any]]] = None,
        embedding_model: str = "nomic-embed-text:latest",
    ):
        """
        Initialize MemoryManager with configurable backends and embedding model.

        Args:
            base_dir: Base directory for backend storage (e.g., SQLite DBs, JSON logs).
            backends: List of backend configurations, each with 'backend' (class) and 'config' (dict).
            embedding_model: Name of the embedding model for VectorBackend.
        """
        self.base_dir = base_dir
        self.embedding_model = embedding_model
        self.ollama_process = None
        self.sessions: Dict[str, Memory] = {}
        self.backends = backends or self._default_backends()
        self._initialize()

    def _default_backends(self) -> List[Dict[str, any]]:
        """Define default backend configurations."""
        return [
            {
                "backend": SQLiteBackend,
                "config": {"db_path": os.path.join(self.base_dir, "{session_id}.db"), "preserve_db": True}
            },
            {
                "backend": FileBackend,
                "config": {"log_path": os.path.join(self.base_dir, "conversation_{session_id}.json")}
            },
            {
                "backend": VectorBackend,
                "config": {
                    "db_path": os.path.join(self.base_dir, "vector_db_{session_id}"),
                    "embedding_model": self.embedding_model
                }
            }
        ]

    def _initialize(self):
        """Initialize ollama resources for embedding model."""
        try:
            # Check if ollama server is running
            try:
                ollama.list()
                logger.info("Ollama server already running")
            except Exception:
                logger.info("Starting ollama server")
                self.ollama_process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                atexit.register(self._stop_ollama)
                time.sleep(5)  # Wait for server to start
                try:
                    ollama.pull(self.embedding_model)
                    logger.info(f"Pulled embedding model {self.embedding_model}")
                except Exception as e:
                    logger.error(f"Failed to pull embedding model {self.embedding_model}: {str(e)}")
                    raise
            logger.info(f"Initialized ollama with model {self.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {str(e)}")
            raise

    def _stop_ollama(self):
        """Clean up ollama resources without shutting down the shared server."""
        if self.ollama_process:
            try:
                logger.info("Stopping ollama server started by MemoryManager")
                self.ollama_process.terminate()
                self.ollama_process.wait(timeout=5)
                logger.debug("Ollama process terminated")
            except subprocess.TimeoutExpired:
                logger.warning("Ollama process did not terminate, killing")
                self.ollama_process.kill()
                try:
                    self.ollama_process.wait(timeout=5)
                    logger.debug("Ollama process killed")
                except subprocess.TimeoutExpired:
                    logger.error("Ollama process could not be killed")
            except Exception as e:
                logger.warning(f"Failed to stop ollama server: {str(e)}")
            finally:
                self.ollama_process = None
        else:
            logger.debug("No ollama process to stop; assuming shared server")

    def get_memory(self, session_id: str) -> Memory:
        """Get or create a Memory instance for the session."""
        if session_id not in self.sessions:
            # Substitute session_id in backend configurations
            session_backends = []
            for backend_config in self.backends:
                backend_class = backend_config["backend"]
                config = backend_config.get("config", {}).copy()
                # Replace {session_id} placeholders in config values
                for key, value in config.items():
                    if isinstance(value, str):
                        config[key] = value.format(session_id=session_id)
                session_backends.append({"backend": backend_class, "config": config})
            self.sessions[session_id] = Memory(session_id=session_id, backends=session_backends)
            logger.debug(f"Created Memory instance for session_id={session_id}")
        return self.sessions[session_id]

    def save(self, prompt: str, response: str, task_id: str, agent_name: str, session_id: str) -> None:
        """Save a conversation to the Memory instance for the session."""
        memory = self.get_memory(session_id)
        memory.save(prompt, response, task_id, agent_name)
        logger.debug(
            f"Saved conversation via MemoryManager: session_id={session_id}, "
            f"task_id={task_id}, agent_name={agent_name}"
        )

    def save_task(self, task: Task, session_id: str) -> None:
        """Save a task to the Memory instance for the session."""
        memory = self.get_memory(session_id)
        memory.save_task(task)
        logger.debug(f"Saved task via MemoryManager: session_id={session_id}, task_id={task.task_id}")

    def load_cached_response(self, prompt_hash: str, session_id: str) -> Optional[str]:
        """Load a cached response for the prompt hash from the session's Memory."""
        memory = self.get_memory(session_id)
        response = memory.load_cached_response(prompt_hash)
        if response:
            logger.debug(
                f"Loaded cached response via MemoryManager: session_id={session_id}, prompt_hash={prompt_hash}"
            )
        return response

    def load_task(self, task_id: str, session_id: str) -> Optional[Task]:
        """Load a task from the session's Memory."""
        memory = self.get_memory(session_id)
        task = memory.load_task(task_id)
        if task:
            logger.debug(f"Loaded task via MemoryManager: session_id={session_id}, task_id={task_id}")
        return task

    def load_history(self, task_id: str, agent_name: str, session_id: str) -> List[Tuple[str, str, str]]:
        """Load conversation history for the task and agent from the session's Memory."""
        memory = self.get_memory(session_id)
        history = memory.load_history(task_id, agent_name)
        logger.debug(
            f"Loaded conversation history via MemoryManager: session_id={session_id}, "
            f"task_id={task_id}, agent_name={agent_name}, count={len(history)}"
        )
        return history

    def stop(self):
        """Signal shutdown of MemoryManager."""
        logger.info("Stopping MemoryManager")
        self._stop_ollama()
        for session_id, memory in list(self.sessions.items()):
            try:
                memory.stop()
            except Exception as e:
                logger.warning(f"Failed to stop session {session_id}: {str(e)}")

    def close(self):
        """Free all resources associated with MemoryManager."""
        logger.info("Closing MemoryManager resources")
        self._stop_ollama()
        for session_id, memory in list(self.sessions.items()):
            try:
                memory.close()
                del self.sessions[session_id]
            except Exception as e:
                logger.warning(f"Failed to close session {session_id}: {str(e)}")
        self.sessions.clear()
