# seclorum/agents/memory/protocol.py
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict
from seclorum.models import Task

class MemoryBackend(ABC):
    """Abstract base class defining the protocol for memory backends."""

    @abstractmethod
    def initialize(self, **kwargs) -> None:
        """Initialize the backend with optional configuration."""
        pass

    @abstractmethod
    def save_conversation(
        self, session_id: str, task_id: str, agent_name: str, prompt: str, response: str
    ) -> None:
        """Save a conversation to the backend."""
        pass

    @abstractmethod
    def load_conversation_history(
        self, session_id: str, task_id: str, agent_name: str
    ) -> List[Tuple[str, str, str]]:
        """Load conversation history for the session, task, and agent."""
        pass

    @abstractmethod
    def load_cached_response(self, session_id: str, prompt_hash: str) -> Optional[str]:
        """Load a cached response for the prompt hash."""
        pass

    @abstractmethod
    def cache_response(self, session_id: str, prompt_hash: str, response: str) -> None:
        """Cache a response for the prompt hash."""
        pass

    @abstractmethod
    def save_task(self, session_id: str, task_id: str, task_data: Dict) -> None:
        """Save a task to the backend."""
        pass

    @abstractmethod
    def load_task(self, session_id: str, task_id: str) -> Optional[Dict]:
        """Load a task from the backend."""
        pass

    @abstractmethod
    def find_similar(
        self, text: str, session_id: str, task_id: str, n_results: int
    ) -> List[Dict]:
        """Find similar conversations in the backend."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Signal shutdown of the backend."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close backend resources."""
        pass
