# seclorum/agents/memory/manager.py
import os
import logging
import json
from datetime import datetime
import chromadb
import ollama
import subprocess
import atexit
from typing import List, Dict, Optional, Tuple
from seclorum.models import Task
from seclorum.agents.memory.memory import Memory
from seclorum.agents.memory.vector import VectorBackend

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, base_dir: str = "agents/logs/conversations", vector_db_path: str = None, embedding_model: str = None):
        self.base_dir = base_dir
        self.vector_db_path = vector_db_path or "/var/folders/2p/jyc0xwzx5wn8tkn6032dkfth0000gn/T/chroma_db"
        self.embedding_model = embedding_model or "nomic-embed-text:latest"
        self.vector_db = None
        self.ollama_process = None
        self.sessions: Dict[str, Memory] = {}
        self._initialize()

    def _initialize(self):
        """Initialize chromadb and ollama resources."""
        try:
            # Initialize chromadb
            self.vector_db = chromadb.PersistentClient(path=self.vector_db_path, settings=chromadb.Settings(anonymized_telemetry=False))
            logger.info("Initialized chromadb client")
            # Start ollama server if not running
            try:
                ollama.list()
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
        """Stop the ollama server subprocess."""
        if self.ollama_process:
            try:
                logger.info("Stopping ollama server")
                self.ollama_process.terminate()
                self.ollama_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Ollama process did not terminate, killing")
                self.ollama_process.kill()
            except Exception as e:
                logger.warning(f"Failed to stop ollama server: {str(e)}")
            finally:
                self.ollama_process = None

    def get_memory(self, session_id: str) -> Memory:
        """Get or create a Memory instance for the session."""
        if session_id not in self.sessions:
            sqlite_db_path = os.path.join(self.base_dir, f"{session_id}.db")
            log_path = os.path.join(self.base_dir, f"conversation_{session_id}.json")
            vector_backend = VectorBackend(self.vector_db_path)
            self.sessions[session_id] = Memory(
                session_id=session_id,
                sqlite_db_path=sqlite_db_path,
                log_path=log_path,
                vector_backend=vector_backend,
                embedding_model=self.embedding_model
            )
        return self.sessions[session_id]

    def save(self, prompt: str, response: str, task_id: str, agent_name: str, session_id: str) -> None:
        """Save a conversation to the Memory instance for the session."""
        memory = self.get_memory(session_id)
        memory.save(prompt, response, task_id, agent_name)
        logger.debug(f"Saved conversation via MemoryManager: session_id={session_id}, task_id={task_id}, agent_name={agent_name}")

    def load_cached_response(self, prompt_hash: str, session_id: str) -> Optional[str]:
        """Load a cached response for the prompt hash from the session's Memory."""
        memory = self.get_memory(session_id)
        response = memory.load_cached_response(prompt_hash)
        if response:
            logger.debug(f"Loaded cached response via MemoryManager: session_id={session_id}, prompt_hash={prompt_hash}")
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
        logger.debug(f"Loaded conversation history via MemoryManager: session_id={session_id}, task_id={task_id}, agent_name={agent_name}, count={len(history)}")
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
        if self.vector_db:
            try:
                self.vector_db = None  # Let Python GC handle chromadb cleanup
                logger.info("Closed chromadb client")
            except Exception as e:
                logger.warning(f"Failed to close chromadb client: {str(e)}")
        self.sessions.clear()
