# tests/test_executor.py
import os
import logging
import unittest
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.models.manager import create_model_manager

class TestExecutor(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("TestExecutor")
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not self.api_key:
            self.skipTest("Skipping test: GOOGLE_AI_STUDIO_API_KEY not set in environment")

        self.session_id = "test_executor_session"
        self.model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.developer = Developer(self.session_id, self.model_manager)

        # Inject API key for remote inference
        for agent in self.developer.agents.values():
            agent.REMOTE_ENDPOINTS["google_ai_studio"]["api_key"] = self.api_key

        # Define a Three.js task to force Puppeteer execution
        self.task = Task(
            task_id="puppeteer_test",
            description="Create a simple Three.js JavaScript scene with a rotating cube.",
            parameters={"language": "javascript", "use_remote": True, "generate_tests": True}
        )

    def test_puppeteer_execution(self):
        self.logger.info("Starting Puppeteer execution test")

        # Run the developer workflow
        status, result = self.developer.process_task(self.task)

        # Log the final state
        self.logger.info(f"Task completed with status: {status}")
        self.logger.info(f"Final result type: {type(result).__name__}, content: {result}")

        # Check Generator output
        generator_key = next((k for k in self.task.parameters if k.startswith("Generator_")), None)
        generator_output = self.task.parameters.get(generator_key, {}).get("result")
        self.assertIsNotNone(generator_output, "Generator output should be present")
        self.assertIsInstance(generator_output, CodeOutput, "Generator should return CodeOutput")
        self.assertTrue(generator_output.code.strip(), "Generated code should not be empty")
        self.logger.info(f"Generated code:\n{generator_output.code}")

        # Check Executor output
        executor_key = next((k for k in self.task.parameters if k.startswith("Executor_")), None)
        executor_output = self.task.parameters.get(executor_key, {}).get("result") if executor_key else None

        self.assertIsNotNone(executor_output, "Executor should have run with generate_tests=True")
        self.assertIsInstance(executor_output, TestResult, "Executor should return TestResult")
        self.logger.info(f"Executor result: passed={executor_output.passed}, output={executor_output.output}")

        if not executor_output.passed:
            self.assertTrue(executor_output.output.strip(), "Executor should provide a meaningful error message")
        else:
            self.assertTrue(executor_output.passed, "Executor should pass with valid Puppeteer execution")

    def tearDown(self):
        self.logger.info("Test completed")

if __name__ == "__main__":
    unittest.main()
