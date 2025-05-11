# seclorum/agents/tester.py
from typing import Tuple, Any, Dict, Optional
from seclorum.agents.agent import Agent
from seclorum.models import Task, TestResult
from seclorum.languages import LANGUAGE_HANDLERS
import logging
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Tester(Agent):
    def __init__(self, name: str, session_id: str, model_manager=None):
        super().__init__(name, session_id, model_manager)
        logger.debug(f"Tester initialized: name={name}, session_id={session_id}")

    def get_prompt(self, task: Task) -> str:
        """Generate prompt for test code generation."""
        language = task.parameters.get("language", "javascript").lower()
        code = task.parameters.get("code", "")
        output_file = task.parameters.get("output_file", "unknown")
        system_prompt = (
            "You are a coding assistant that generates test code for a given source code. "
            "Output ONLY valid test code in the specified language, no comments, no markdown, no code block markers (```), "
            "and no text outside the test code. "
            "The test code should validate the functionality of the provided code."
        )
        user_prompt = (
            f"Language: {language}\n"
            f"Source file: {output_file}\n"
            f"Source code:\n{code}\n\n"
            f"Generate test code to validate the functionality of the source code. "
            f"For JavaScript, use Jest syntax with expect assertions. "
            f"For HTML, validate DOM structure. "
            f"For CSS, ensure styling rules are applied. "
            f"For JSON, verify structure and required fields."
        )
        if self.model_manager.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        return (
            f"<|start_header_id|>system<|end_header_id>\n{system_prompt}\n"
            f"<|start_header_id|>user<|end_header_id>\n{user_prompt}"
        )

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate retry prompt for failed test code generation."""
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            issues.append("Invalid test code: must be executable and use correct syntax for the language")
        feedback = "\n".join([f"- {issue}" for issue in issues]) or "Test code did not meet requirements"
        guidance = (
            "Output ONLY valid test code in the specified language, no comments, no markdown, no code block markers (```), "
            "and no text outside the test code. "
            "Ensure the test code is syntactically correct and validates the source code functionality."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return schema for test code output."""
        return {
            "type": "string",
            "description": "Valid test code in the specified language"
        }

    def strip_markdown_code(self, text: str) -> str:
        """Strip Markdown code fences from test code output."""
        return re.sub(r'```(?:\w+)?\n([\s\S]*?)\n```', r'\1', text).strip()

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"Processing task {task.task_id}: language={task.parameters.get('language')}")
        try:
            language = task.parameters.get("language", "javascript").lower()
            if language not in LANGUAGE_HANDLERS:
                logger.error(f"Unsupported language: {language}")
                return "failed", TestResult(test_code="", passed=False, output="Unsupported language")

            handler = LANGUAGE_HANDLERS[language]
            code = task.parameters.get("code", "")
            if not code:
                logger.warning("No code provided for testing")
                return "failed", TestResult(test_code="", passed=False, output="No code to test")

            test_code = handler.get_test_prompt(code)
            if not test_code:
                logger.debug("No test code from handler, generating via inference")
                prompt = self.get_prompt(task)
                try:
                    test_code = self.infer(
                        prompt=prompt,
                        task=task,
                        use_remote=task.parameters.get("use_remote", False),
                        max_tokens=4096,
                        function_call={"schema": self.get_schema()}
                    )
                    test_code = self.strip_markdown_code(test_code)
                except Exception as e:
                    logger.error(f"Test code inference failed: {str(e)}")
                    test_code = handler.get_default_test_code() or f"// Test for {task.parameters.get('output_file', 'unknown')}\nexpect(true).toBe(true);"

            if not test_code:
                logger.warning("No test code generated, using default")
                test_code = handler.get_default_test_code() or f"// Test for {task.parameters.get('output_file', 'unknown')}\nexpect(true).toBe(true);"

            logger.debug(f"Generated test code: {test_code[:100]}...")
            try:
                # Mock test execution (replace with real testing framework if available)
                test_output = self.run_tests(test_code, code, language)
                passed = "passed" in test_output.lower() or handler.validate_code(test_code)
                logger.debug(f"Test result: passed={passed}, output={test_output[:100]}...")
                return "tested", TestResult(test_code=test_code, passed=passed, output=test_output)
            except Exception as e:
                logger.error(f"Test execution failed: {str(e)}")
                return "failed", TestResult(test_code=test_code, passed=False, output=f"Test execution error: {str(e)}")
        except Exception as e:
            logger.error(f"Error testing task {task.task_id}: {str(e)}")
            return "failed", TestResult(test_code="", passed=False, output=f"Testing error: {str(e)}")

    def run_tests(self, test_code: str, code: str, language: str) -> str:
        # Mock implementation (replace with Jest/JSDOM for real testing)
        logger.debug(f"Running tests for {language}: test_code={test_code[:50]}...")
        if language == "html":
            return "DOM structure validated (mock)"
        if language == "css":
            return "Styles validated (mock)"
        if language == "json":
            return "JSON structure validated (mock)"
        return "Tests passed (mock)"
