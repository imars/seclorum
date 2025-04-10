# tests/test_remote_agent.py
import unittest
import os
import logging
from seclorum.agents.base import Agent
from seclorum.models.manager import MockModelManager  # Use mock for fallback

class TestRemoteAgent(unittest.TestCase):
    def setUp(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TestRemoteAgent")

        # Ensure API key is available
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not self.api_key:
            self.skipTest("Skipping test: GOOGLE_AI_STUDIO_API_KEY not set in environment")

        # Configure the agent with a mock model manager to avoid Ollama dependency
        self.agent = Agent(
            name="TestRemote",
            session_id="test_remote_session",
            model_manager=MockModelManager("mock")  # Use mock instead of Ollama
        )

        # Set the API key in the Remote mixin’s configuration
        self.agent.REMOTE_ENDPOINTS["google_ai_studio"]["api_key"] = self.api_key

    def test_remote_inference(self):
        """Test basic remote inference with Google AI Studio."""
        prompt = "Hello, please respond with 'Hi there!'"
        self.logger.info("Starting remote inference test")

        # Perform remote inference
        result = self.agent.infer(
            prompt=prompt,
            use_remote=True,
            endpoint="google_ai_studio",
            max_tokens=20  # Keep it small to minimize rate limit impact
        )

        self.logger.info(f"Remote inference result: {result}")

        # Basic assertion: check we got a response
        self.assertIsNotNone(result, "Remote inference returned None")
        self.assertTrue(isinstance(result, str), "Result should be a string")
        self.assertTrue(len(result.strip()) > 0, "Result should not be empty")

        # Optional: Check expected response (adjust based on actual API behavior)
        expected = "Hi there!"
        self.assertEqual(result.strip(), expected, f"Expected '{expected}', got '{result}'")

    def tearDown(self):
        self.logger.info("Remote inference test completed")

if __name__ == "__main__":
    unittest.main()
