# seclorum/agents/memory_manager.py
from typing import Optional, List, Dict
from seclorum.models import Task
from seclorum.agents.memory.core import ConversationMemory

class MemoryManager:
    def __init__(self, session_id: str):
        self.memory = ConversationMemory(session_id=session_id)

    def save(self, prompt: Optional[str] = None, response: Optional[str] = None, task_id: Optional[str] = None):
        self.memory.save(prompt=prompt, response=response, task_id=task_id)
        self.process_embedding_queue()

    def load_history(self, task_id: Optional[str] = None) -> List[Dict]:
        """Load raw conversation history as a list of dicts."""
        return self.memory.load_conversation_history(task_id=task_id)

    def format_history(self, task_id: Optional[str] = None) -> str:
        """Format history for display."""
        history = self.load_history(task_id=task_id)
        return self.memory.format_history(history)

    def process_embedding_queue(self):
        self.memory.process_embedding_queue()
