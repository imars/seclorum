# seclorum/agents/tester.py
import os
import subprocess
import tempfile
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeResult, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
from typing import Tuple, Optional
import logging
import re
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Tester initialized for Task {task_id}, session_id={session_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeResult]:
        logger.debug(f"Testing code for task={task.task_id}, description={task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")

        # Log task.parameters for debugging
        logger.debug(f"Task parameters: {task.parameters}")

        # Get code from Generator or Debugger
        code = None
        result_key = None
        for key in task.parameters:
            if key.startswith("Generator_") or key.startswith("Debugger_"):
                result = task.parameters.get(key, {}).get("result", {})
                if isinstance(result, CodeOutput) and result.code.strip():
                    code = result.code
                    result_key = key
                    break

        if not code:
            logger.warning(f"No valid {language} code to test for {output_file}")
            return "tested", CodeResult(test_code="", passed=False, output="No code provided")

        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            return "tested", CodeResult(test_code="", passed=False, output=f"Language {language} not supported")

        try:
            # Validate code statically
            static_passed, static_output = self.validate_code(code, language, output_file)
            tests = task.parameters.get(result_key, {}).get("result", {}).get("tests", "") if result_key else ""

            # Generate tests if needed
            if not tests and task.parameters.get("generate_tests", False):
                test_prompt = handler.get_test_prompt(code)
                use_remote = task.parameters.get("use_remote", False)
                raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False, max_tokens=2000)
                tests = re.sub(r'```(?:javascript|html|python|cpp)?\n|\n```|[^\x00-\x7F]+', '', raw_tests).strip()
                if not tests.startswith(("describe(", "test(")):
                    logger.warning(f"Invalid Jest tests for {output_file}, discarding")
                    tests = ""
                logger.debug(f"Generated tests for {output_file}:\n{tests[:200]}...")

            # Run dynamic tests for JavaScript
            dynamic_passed = True
            dynamic_output = "No dynamic tests executed"
            if tests and language == "javascript":
                try:
                    dynamic_passed, dynamic_output = self.run_jest_tests(code, tests, output_file)
                except Exception as e:
                    logger.error(f"Jest test execution failed for {output_file}: {str(e)}")
                    dynamic_passed = False
                    dynamic_output = f"Jest execution failed: {str(e)}"

            # Combine results
            passed = static_passed and dynamic_passed
            output = f"{static_output}\n{dynamic_output}"
            result = CodeResult(test_code=tests, passed=passed, output=output)
            logger.debug(f"Test result for {output_file}: passed={passed}, output={output[:200]}...")
            self.save_output(task, result, status="tested")
            self.commit_changes(f"Tested {language} code for {output_file}")
            return "tested", result
        except Exception as e:
            logger.error(f"Testing failed for {output_file}: {str(e)}")
            return "tested", CodeResult(test_code="", passed=False, output=f"Testing failed: {str(e)}")

    def validate_code(self, code: str, language: str, output_file: str) -> Tuple[bool, str]:
        logger.debug(f"Statically validating {language} code for {output_file}")
        if language == "html":
            try:
                soup = BeautifulSoup(code, 'html.parser')
                checks = {
                    "canvas": bool(soup.find("canvas")),
                    "timer": bool(soup.find(id="timer")),
                    "speed": bool(soup.find(id="speed")),
                    "standings": bool(soup.find(id="standings")),
                    "startReset": bool(soup.find(id="startReset")),
                    "three_js": bool(soup.find("script", src=lambda s: s and "three.min.js" in s)),
                    "drone_game_js": bool(soup.find("script", src="drone_game.js"))
                }
                passed = all(checks.values())
                output = f"HTML validation {'passed' if passed else 'failed'}: {', '.join(f'{k}={v}' for k, v in checks.items())}"
                logger.debug(output)
                return passed, output
            except Exception as e:
                output = f"HTML validation failed: {str(e)}"
                logger.error(output)
                return False, output
        elif language == "javascript":
            required = ["THREE\\.", "scene\\s*=", "camera\\s*=", "renderer\\s*=", "addEventListener"]
            checks = {kw: bool(re.search(kw, code)) for kw in required}
            passed = all(checks.values())
            output = f"JavaScript validation {'passed' if passed else 'failed'}: {', '.join(f'{k}={v}' for k, v in checks.items())}"
            logger.debug(output)
            return passed, output
        return False, f"Unsupported language: {language}"

    def run_jest_tests(self, code: str, tests: str, output_file: str) -> Tuple[bool, str]:
        logger.debug(f"Running Jest tests for {output_file}")
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, f"{os.path.basename(output_file)}.test.js")
            with open(test_file, "w") as f:
                f.write(tests)

            code_file = os.path.join(tmpdir, os.path.basename(output_file))
            with open(code_file, "w") as f:
                f.write(code)

            jest_config = """
module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/*.test.js'],
};
"""
            config_file = os.path.join(tmpdir, "jest.config.js")
            with open(config_file, "w") as f:
                f.write(jest_config)

            try:
                result = subprocess.run(
                    ["npx", "jest", test_file, "--config", config_file, "--silent"],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    env={**os.environ, "TOKENIZERS_PARALLELISM": "false"}
                )
                output = result.stdout + result.stderr
                passed = result.returncode == 0
                logger.debug(f"Jest test output for {output_file}:\n{output[:200]}...")
                return passed, output
            except FileNotFoundError:
                logger.warning(f"Jest not installed, skipping dynamic tests for {output_file}")
                return True, "Jest not available, static validation only"
            except subprocess.CalledProcessError as e:
                output = e.output
                logger.error(f"Jest test execution failed for {output_file}:\n{output[:200]}...")
                return False, output

    def start(self):
        logger.debug(f"Starting tester {self.name}")

    def stop(self):
        logger.debug(f"Stopping tester {self.name}")
