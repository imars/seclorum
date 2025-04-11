# seclorum/agents/memory_manager.py
from typing import Optional, List, Dict
from seclorum.models import Task
from seclorum.agents.memory.core import ConversationMemory
import logging
import sqlite3
import os


class MemoryManager:
    _transformer_cache = None

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.logger = logging.getLogger("Seclorum")
        self.db_path = f"seclorum/logs/conversations/conversations_{session_id}.db"
        self.embedding_path = f"seclorum/logs/conversations/embeddings_{session_id}.npy"
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.initialize_db()
        self.model = self.get_or_create_transformer()

    @classmethod
    def get_or_create_transformer(cls):
        if cls._transformer_cache is None:
            cls._transformer_cache = SentenceTransformer("all-MiniLM-L6-v2")
            cls._transformer_cache.to("cpu")
            logging.getLogger("Seclorum").info("Loaded SentenceTransformer: all-MiniLM-L6-v2")
        return cls._transformer_cache

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
