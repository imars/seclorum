import unittest
import os
import sys
import argparse
import logging
from seclorum.memory.core import ConversationMemory

parser = argparse.ArgumentParser(description="Run memory tests for Seclorum")
parser.add_argument('--debug', action='store_true', help='Enable debug logging')
args = parser.parse_args()
logging.getLogger("Seclorum").setLevel(logging.DEBUG if args.debug else logging.INFO)

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.session_id1 = "test_session_123"
        self.session_id2 = "test_session_456"
        self.memory1 = ConversationMemory(self.session_id1)
        self.log_file1 = f"logs/conversations/conversation_{self.session_id1}.json"
        self.log_file2 = f"logs/conversations/conversation_{self.session_id2}.json"
        for f in [self.log_file1, self.log_file2]:
            if os.path.exists(f):
                os.remove(f)

    def tearDown(self):
        for f in [self.log_file1, self.log_file2]:
            if os.path.exists(f):
                os.remove(f)

    def test_cross_session_memory(self):
        self.memory1.save(prompt="Hello, how are you?")
        self.memory1.save(response="I'm doing great, thanks!")
        self.memory1.process_embedding_queue()
        memory2 = ConversationMemory(self.session_id2)
        memory2.save(prompt="Checking previous chats")
        # Query from session2, should find session1's data
        results = memory2.query_memory("how are you", n_results=2)
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("Hello, how are you?", results[0]["text"])
        history = self.memory1.load_conversation_history()  # Still session-specific
        self.assertIn("User: Hello, how are you?", history)
        self.assertIn("Agent: I'm doing great, thanks!", history)

    def test_async_embedding(self):
        self.memory1.save(prompt="Async test prompt")
        self.assertEqual(len(self.memory1.embedding_queue), 1)
        self.memory1.process_embedding_queue()
        self.assertEqual(len(self.memory1.embedding_queue), 0)
        results = self.memory1.query_memory("Async test", n_results=1)
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("Async test prompt", results[0]["text"])

if __name__ == "__main__":
    runner = unittest.TextTestRunner()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMemory)
    runner.run(suite)
