# seclorum/agents/memory/memory.py
import logging
from typing import List, Optional, Tuple, Dict
from seclorum.models import Task
from seclorum.agents.memory.protocol import MemoryBackend

logger = logging.getLogger(__name__)

class Memory:
    def __init__(
        self,
        session_id: str,
        backends: List[Dict[str, any]],
    ):
        """
        Initialize Memory with a list of backend configurations.

        Args:
            session_id: Unique identifier for the session.
            backends: List of dictionaries, each containing 'backend' (MemoryBackend class)
                      and 'config' (dict of initialization parameters).
        """
        self.session_id = session_id
        self.backends: List[MemoryBackend] = []
        self._initialize_backends(backends)

    def _initialize_backends(self, backends: List[Dict[str, any]]) -> None:
        """Initialize all configured backends."""
        for backend_config in backends:
            backend_class = backend_config.get("backend")
            config = backend_config.get("config", {})
            if not isinstance(backend_class, type) or not issubclass(backend_class, MemoryBackend):
                logger.error(f"Invalid backend class: {backend_class}")
                continue
            try:
                backend_instance = backend_class(**config)
                backend_instance.initialize(**config)
                self.backends.append(backend_instance)
                logger.info(f"Initialized backend: {backend_class.__name__}")
            except Exception as e:
                logger.error(f"Failed to initialize backend {backend_class.__name__}: {str(e)}")
                raise

    def save(self, prompt: str, response: str, task_id: str, agent_name: str) -> None:
        """Save a conversation to all backends."""
        for backend in self.backends:
            try:
                backend.save_conversation(
                    session_id=self.session_id,
                    task_id=task_id,
                    agent_name=agent_name,
                    prompt=prompt,
                    response=response,
                )
                logger.debug(
                    f"Saved conversation to {backend.__class__.__name__}: "
                    f"session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}"
                )
            except Exception as e:
                logger.warning(f"Failed to save to {backend.__class__.__name__}: {str(e)}")

    def load_history(self, task_id: str, agent_name: str) -> List[Tuple[str, str, str]]:
        """Load conversation history from the first backend that succeeds."""
        for backend in self.backends:
            try:
                history = backend.load_conversation_history(
                    session_id=self.session_id,
                    task_id=task_id,
                    agent_name=agent_name,
                )
                logger.debug(
                    f"Loaded conversation history from {backend.__class__.__name__}: "
                    f"session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}, count={len(history)}"
                )
                return history
            except Exception as e:
                logger.warning(f"Failed to load history from {backend.__class__.__name__}: {str(e)}")
        return []

    def load_cached_response(self, prompt_hash: str) -> Optional[str]:
        """Load a cached response from the first backend that succeeds."""
        for backend in self.backends:
            try:
                response = backend.load_cached_response(
                    session_id=self.session_id,
                    prompt_hash=prompt_hash,
                )
                if response:
                    logger.debug(
                        f"Loaded cached response from {backend.__class__.__name__}: "
                        f"session_id={self.session_id}, prompt_hash={prompt_hash}"
                    )
                    return response
            except Exception as e:
                logger.warning(f"Failed to load cached response from {backend.__class__.__name__}: {str(e)}")
        return None

    def cache_response(self, prompt_hash: str, response: str) -> None:
        """Cache a response in all backends."""
        for backend in self.backends:
            try:
                backend.cache_response(
                    session_id=self.session_id,
                    prompt_hash=prompt_hash,
                    response=response,
                )
                logger.debug(
                    f"Cached response in {backend.__class__.__name__}: "
                    f"session_id={self.session_id}, prompt_hash={prompt_hash}"
                )
            except Exception as e:
                logger.warning(f"Failed to cache response in {backend.__class__.__name__}: {str(e)}")

    def save_task(self, task: Task) -> None:
        """Save a task to all backends."""
        task_data = task.dict()
        for backend in self.backends:
            try:
                backend.save_task(
                    session_id=self.session_id,
                    task_id=task.task_id,
                    task_data=task_data,
                )
                logger.debug(
                    f"Saved task to {backend.__class__.__name__}: "
                    f"session_id={self.session_id}, task_id={task.task_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to save task to {backend.__class__.__name__}: {str(e)}")

    def load_task(self, task_id: str) -> Optional[Task]:
        """Load a task from the first backend that succeeds."""
        for backend in self.backends:
            try:
                task_data = backend.load_task(
                    session_id=self.session_id,
                    task_id=task_id,
                )
                if task_data:
                    logger.debug(
                        f"Loaded task from {backend.__class__.__name__}: "
                        f"session_id={self.session_id}, task_id={task_id}"
                    )
                    return Task(**task_data)
                return None
            except Exception as e:
                logger.warning(f"Failed to load task from {backend.__class__.__name__}: {str(e)}")
        return None

    def find_similar(self, text: str, task_id: str, n_results: int = 5, session_id: Optional[str] = None) -> List[Dict]:
        """Find similar conversations from backends that support similarity search."""
        session_id = session_id or self.session_id
        for backend in self.backends:
            try:
                results = backend.find_similar(
                    text=text,
                    session_id=session_id,
                    task_id=task_id,
                    n_results=n_results,
                )
                if results:
                    logger.debug(
                        f"Found {len(results)} similar conversations from {backend.__class__.__name__}: "
                        f"task_id={task_id}"
                    )
                    return results
            except Exception as e:
                logger.warning(f"Failed to find similar in {backend.__class__.__name__}: {str(e)}")
        logger.warning("No backend returned similar conversations")
        return []

    def stop(self):
        """Signal shutdown of all backends."""
        for backend in self.backends:
            try:
                backend.stop()
                logger.info(f"Stopped {backend.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to stop {backend.__class__.__name__}: {str(e)}")

    def close(self):
        """Close all backend resources."""
        for backend in self.backends:
            try:
                backend.close()
                logger.info(f"Closed {backend.__class__.__name__}")
            except Exception as e:
                logger.warning(f"Failed to close {backend.__class__.__name__}: {str(e)}")
