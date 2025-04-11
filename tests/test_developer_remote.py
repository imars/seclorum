# tests/test_developer_remote.py (updated)
import unittest
import os
import logging
from seclorum.agents.developer import Developer
from seclorum.models import Task, create_model_manager, CodeOutput

class TestDeveloperRemote(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TestDeveloperRemote")
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not self.api_key:
            self.skipTest("Skipping test: GOOGLE_AI_STUDIO_API_KEY not set in environment")
        self.session_id = "test_developer_remote_session"
        self.model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.developer = Developer(self.session_id, self.model_manager)
        for agent in self.developer.agents.values():
            agent.REMOTE_ENDPOINTS["google_ai_studio"]["api_key"] = self.api_key

    def test_simple_js_function(self):
        self.logger.info("Starting Developer remote inference test")
        task = Task(
            task_id="simple_js_add",
            description="Create a JavaScript function that adds two numbers and returns the sum.",
            parameters={
                "language": "javascript",
                "use_remote": True,
                "generate_tests": False
            }
        )
        status, result = self.developer.process_task(task)
        self.logger.info(f"Task completed with status: {status}")
        self.logger.info(f"Generated result: {result}")

        self.assertEqual(status, "generated", "Expected task to complete at 'generated' status")
        self.assertIsInstance(result, CodeOutput, "Result should be a CodeOutput object")
        self.assertTrue(hasattr(result, "code"), "Result should have a 'code' attribute")
        self.assertTrue("function" in result.code, "Code should contain a function definition")
        self.assertTrue("return" in result.code, "Code should contain a return statement")
        self.assertTrue("+" in result.code, "Code should perform addition")
        self.logger.info(f"Generated JavaScript code:\n{result.code}")

    def tearDown(self):
        self.logger.info("Developer remote inference test completed")

if __name__ == "__main__":
    unittest.main()
