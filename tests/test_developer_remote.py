# tests/test_developer_remote.py
import unittest
import os
import logging
from seclorum.agents.developer import Developer
from seclorum.models import Task, create_model_manager, CodeOutput

class TestDeveloperRemote(unittest.TestCase):
    def setUp(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TestDeveloperRemote")

        # Ensure API key is available
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not self.api_key:
            self.skipTest("Skipping test: GOOGLE_AI_STUDIO_API_KEY not set in environment")

        # Initialize Developer with a session and model manager
        self.session_id = "test_developer_remote_session"
        self.model_manager = create_model_manager(provider="ollama", model_name="codellama")
        self.developer = Developer(self.session_id, self.model_manager)

        # Set API key in Remote configuration
        for agent in self.developer.agents.values():
            agent.REMOTE_ENDPOINTS["google_ai_studio"]["api_key"] = self.api_key

    def test_simple_js_function(self):
        """Test Developer generating a simple JS function with remote inference."""
        self.logger.info("Starting Developer remote inference test")

        # Define a simple task
        task = Task(
            task_id="simple_js_add",
            description="Create a JavaScript function that adds two numbers and returns the sum.",
            parameters={
                "language": "javascript",
                "use_remote": True,  # Force remote inference
                "generate_tests": False  # Skip testing for simplicity
            }
        )

        # Run the task through Developer
        status, result = self.developer.process_task(task)
        self.logger.info(f"Task completed with status: {status}")
        self.logger.info(f"Generated result: {result}")

        # Assertions
        self.assertEqual(status, "generated", "Expected task to complete at 'generated' status")
        self.assertIsInstance(result, CodeOutput, "Result should be a CodeOutput object")
        self.assertTrue(hasattr(result, "code"), "Result should have a 'code' attribute")
        self.assertTrue("function" in result.code, "Code should contain a function definition")
        self.assertTrue("return" in result.code, "Code should contain a return statement")
        self.assertTrue("+" in result.code, "Code should perform addition")

        # Log the generated code for verification
        self.logger.info(f"Generated JavaScript code:\n{result.code}")

    def tearDown(self):
        self.logger.info("Developer remote inference test completed")

if __name__ == "__main__":
    unittest.main()
