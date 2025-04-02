# seclorum/agents/memory_manager.py
from seclorum.agents.memory.core import ConversationMemory  # Updated import

class MemoryManager:
    def __init__(self, session_id):
        self.memory = ConversationMemory(session_id=session_id)

    def save(self, prompt=None, response=None, task_id=None):
        self.memory.save(prompt=prompt, response=response, task_id=task_id)

    def process_embeddings(self):
        self.memory.process_embedding_queue()

    def load_history(self, task_id=None):
        return self.memory.load_conversation_history(task_id=task_id)
