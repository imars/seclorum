# seclorum/agents/memory_manager.py
from typing import Optional
from seclorum.models import Task
from seclorum.agents.memory.core import ConversationMemory
from typing import List

class MemoryManager:
    def __init__(self, session_id: str):
        self.memory = ConversationMemory(session_id=session_id)

    def save(self, prompt: Optional[str] = None, response: Optional[str] = None, task_id: Optional[str] = None):
        self.memory.save(prompt=prompt, response=response, task_id=task_id)
        self.process_embedding_queue()  # Ensure embeddings are processed

    def load_history(self, task_id: Optional[str] = None) -> List[str]:
        """Load conversation history as a list of response strings."""
        history_str = self.memory.load_conversation_history(task_id=task_id)
        # Split on a delimiter (assuming newlines separate entries; adjust if different)
        return [entry.strip() for entry in history_str.split("\n\n") if entry.strip()]
        # Note: If ConversationMemory can return a list directly, we’d modify it there instead

    def process_embedding_queue(self):
        self.memory.process_embedding_queue()
