import unittest
import os
from seclorum.memory.core import ConversationMemory

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session_123"
        self.memory = ConversationMemory(self.session_id)
        self.log_file = f"logs/conversations/conversation_{self.session_id}.json"
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def test_save_and_load(self):
        self.memory.save(prompt="Test prompt")
        self.memory.save(response="Test response")
        self.memory.save(session_id=self.session_id)
        
        reloaded = ConversationMemory(self.session_id)
        self.assertEqual(len(reloaded.log["prompts"]), 1)
        self.assertEqual(reloaded.log["prompts"][0]["text"], "Test prompt")
        self.assertEqual(len(reloaded.log["responses"]), 1)
        self.assertEqual(reloaded.log["responses"][0]["text"], "Test response")
        self.assertEqual(len(reloaded.log["sessions"]), 1)
        self.assertEqual(reloaded.log["sessions"][0]["id"], self.session_id)

    def test_summary(self):
        self.memory.save(prompt="Prompt 1")
        self.memory.save(response="Response 1")
        summary = self.memory.get_summary(limit=1)
        self.assertIn("Prompt 1", summary)
        self.assertIn("Response 1", summary)
        self.assertIn(self.session_id, summary)

if __name__ == "__main__":
    unittest.main()
