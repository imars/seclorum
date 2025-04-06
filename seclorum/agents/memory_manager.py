# seclorum/agents/memory_manager.py
from typing import Optional
from seclorum.models import Task
from seclorum.agents.memory.core import ConversationMemory

class MemoryManager:
    def __init__(self, session_id: str):
        self.memory = ConversationMemory(session_id=session_id)

    def save(self, prompt: Optional[str] = None, response: Optional[str] = None, task_id: Optional[str] = None):
            self.memory.save(prompt=prompt, response=response, task_id=task_id)

    def load_history(self, task_id: Optional[str] = None) -> str:
        return self.memory.load_conversation_history(task_id=task_id)

    def process_embedding_queue(self):
        self.memory.process_embedding_queue()
