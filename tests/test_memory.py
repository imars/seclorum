# tests/test_memory.py
import unittest
import os
import logging
import json
import uuid
import tempfile
import threading
import time
import numpy as np
from seclorum.agents.memory.manager import MemoryManager
from seclorum.models import Task

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.vector_db_path = os.path.join(tempfile.gettempdir(), f"test_chroma_db_{uuid.uuid4()}")
        self.manager = MemoryManager(
            base_dir="agents/logs/conversations",
            vector_db_path=self.vector_db_path,
            embedding_model="nomic-embed-text:latest:ollama"
        )
        self.session_id1 = f"test_session_{uuid.uuid4()}"
        self.session_id2 = f"test_session_{uuid.uuid4()}"
        self.task_id = "test_task"
        self.agent_name = "test_agent"
        self.log_file1 = f"agents/logs/conversations/conversation_{self.session_id1}.json"
        self.log_file2 = f"agents/logs/conversations/conversation_{self.session_id2}.json"
        self.saved_prompts = set()
        self.save_lock = threading.Lock()
        for f in [self.log_file1, self.log_file2]:
            if os.path.exists(f):
                os.remove(f)

    def tearDown(self):
        self.manager.stop()
        for f in [self.log_file1, self.log_file2]:
            if os.path.exists(f):
                os.remove(f)
        for session_id in [self.session_id1, self.session_id2]:
            db_path = os.path.join(tempfile.gettempdir(), f"memory_{session_id}.db")
            if os.path.exists(db_path):
                os.remove(db_path)
        import shutil
        if os.path.exists(self.vector_db_path):
            shutil.rmtree(self.vector_db_path)

    def test_save_and_load_conversation(self):
        prompt = "Hello, how are you?"
        response = "I'm doing great, thanks!"
        self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)

        # Check SQLite
        history = self.manager.load_history(self.task_id, self.agent_name, self.session_id1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0], prompt)
        self.assertEqual(history[0][1], response)

        # Check log file
        self.assertTrue(os.path.exists(self.log_file1))
        with open(self.log_file1, 'r') as f:
            log_data = json.load(f)
        self.assertEqual(len(log_data), 1)
        self.assertEqual(log_data[0]["prompt"], prompt)
        self.assertEqual(log_data[0]["response"], response)

    def test_cross_session_memory(self):
        prompt = "Hello, how are you?"
        response = "I'm doing great, thanks!"
        memory = self.manager.get_memory(self.session_id1)
        self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)
        time.sleep(10)  # Increased to ensure embedding storage
        # Debug ChromaDB collection
        collection = self.manager.vector_backend.collection
        count = collection.count()
        logger.debug(f"ChromaDB collection size: {count}")
        if count > 0:
            peek = collection.peek(limit=1)
            logger.debug(f"ChromaDB peek: {peek}")
        results = memory.find_similar("how are you", n_results=2)
        self.assertGreaterEqual(len(results), 1, f"No results found, collection size: {count}")
        self.assertIn(prompt, results[0]["text"])
        history = self.manager.load_history(self.task_id, self.agent_name, self.session_id1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0][0], prompt)
        self.assertEqual(history[0][1], response)

    def test_embedding_generation(self):
        prompt = "Async test prompt"
        response = "Async test response"
        memory = self.manager.get_memory(self.session_id1)
        self.manager.save(prompt, response, self.task_id, self.agent_name, self.session_id1)
        time.sleep(10)  # Increased to ensure embedding storage
        # Debug ChromaDB collection
        collection = self.manager.vector_backend.collection
        count = collection.count()
        logger.debug(f"ChromaDB collection size: {count}")
        if count > 0:
            peek = collection.peek(limit=1)
            logger.debug(f"ChromaDB peek: {peek}")
        results = memory.find_similar("Async test", self.task_id, n_results=1)
        self.assertGreaterEqual(len(results), 1, f"No results found, collection size: {count}")
        self.assertIn(prompt, results[0]["text"])

    def test_cache_response(self):
        prompt_hash = "test_hash"
        response = "Cache test response"
        self.manager.cache_response(prompt_hash, response, self.session_id1)
        cached = self.manager.load_cached_response(prompt_hash, self.session_id1)
        self.assertEqual(cached, response)

    def test_save_task(self):
        task = Task(task_id=self.task_id, description="Test task", parameters={"key": "value"})
        self.manager.save_task(task, self.session_id1)
        loaded_task = self.manager.load_task(self.task_id, self.session_id1)
        self.assertIsNotNone(loaded_task)
        self.assertEqual(loaded_task.task_id, self.task_id)
        self.assertEqual(loaded_task.description, "Test task")
        self.assertEqual(loaded_task.parameters, {"key": "value"})

    def test_vector_db_access(self):
        prompt = "Vector test prompt"
        response = "Vector test response"
        memory = self.manager.get_memory(self.session_id1)
        memory.save(prompt, response, self.task_id, self.agent_name)
        time.sleep(10)  # Increased to ensure embedding storage
        collection = self.manager.vector_backend.collection
        count = collection.count()
        logger.debug(f"ChromaDB collection size after save: {count}")
        results = memory.find_similar("Vector test", self.task_id, n_results=1)
        self.assertGreaterEqual(len(results), 1, f"No results found, collection size: {count}")
        self.assertIn(prompt, results[0]["text"])

    def test_embedding_model_switch(self):
        # Test with sentence-transformers
        manager_st = MemoryManager(
            base_dir="agents/logs/conversations",
            vector_db_path=os.path.join(tempfile.gettempdir(), f"test_chroma_db_{uuid.uuid4()}"),
            embedding_model="all-MiniLM-L6-v2:sentence-transformers"
        )
        memory = manager_st.get_memory(self.session_id1)
        prompt = "Switch test prompt"
        response = "Switch test response"
        memory.save(prompt, response, self.task_id, self.agent_name)
        time.sleep(10)  # Increased to ensure embedding storage
        collection = manager_st.vector_backend.collection
        count = collection.count()
        logger.debug(f"ChromaDB collection size (sentence-transformers): {count}")
        results = memory.find_similar("Switch test", self.task_id, n_results=1)
        self.assertGreaterEqual(len(results), 1, f"No results found, collection size: {count}")
        self.assertIn(prompt, results[0]["text"])
        manager_st.stop()

    def test_embedding_dimension(self):
        memory = self.manager.get_memory(self.session_id1)
        prompt = "Dimension test prompt"
        response = "Dimension test response"
        memory.save(prompt, response, self.task_id, self.agent_name)
        time.sleep(10)  # Increased to ensure embedding storage
        collection = self.manager.vector_backend.collection
        count = collection.count()
        logger.debug(f"ChromaDB collection size: {count}")
        if count > 0:
            peek = collection.peek(limit=1)
            embedding = np.array(peek["embeddings"][0])
            logger.debug(f"Embedding dimension: {embedding.shape[0]}")
            self.assertEqual(embedding.shape[0], 768, f"Expected 768 dimensions for nomic-embed-text, got {embedding.shape[0]}")

if __name__ == "__main__":
    unittest.main()
