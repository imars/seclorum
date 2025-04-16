# seclorum/agents/executor.py
import os
import subprocess
import tempfile
from typing import Tuple, Optional
from seclorum.agents.agent import Agent
from seclorum.models import Task, TestResult, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: Optional[ModelManager] = None):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Executor initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        logger.debug(f"Executing code for task: {task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", f"temp_{language}")
        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            return "tested", TestResult(test_code="", passed=False, output=f"Language {language} not supported")

        tester_key = next((k for k in task.parameters if k.startswith("Tester_") and k.endswith("_test")), None)
        generator_key = next((k for k in task.parameters if k.startswith("Generator_") and k.endswith("_gen")), None)
        code_output = None
        test_code = ""
        if tester_key and tester_key in task.parameters:
            test_result = task.parameters[tester_key].get("result")
            if isinstance(test_result, TestResult):
                test_code = test_result.test_code
                if test_result.passed:
                    code_output = task.parameters.get(generator_key, {}).get("result")
        elif generator_key and generator_key in task.parameters:
            code_output = task.parameters[generator_key].get("result")

        if not code_output or not code_output.code.strip():
            logger.warning(f"No valid code to execute for {output_file}")
            return "tested", TestResult(test_code=test_code, passed=False, output="No code provided")

        code = code_output.code
        logger.debug(f"Executing code for {output_file}:\n{code[:200]}...")

        output = "No execution performed"
        passed = False
        if language == "javascript" and test_code:
            with tempfile.TemporaryDirectory() as tmpdir:
                code_file = os.path.join(tmpdir, f"{os.path.basename(output_file)}.js")
                with open(code_file, "w") as f:
                    f.write(code)

                test_file = os.path.join(tmpdir, f"{os.path.basename(output_file)}.test.js")
                with open(test_file, "w") as f:
                    f.write(test_code)

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
                    logger.debug(f"Execution output for {output_file}:\n{output[:200]}...")
                except subprocess.CalledProcessError as e:
                    output = e.output
                    passed = False
                    logger.error(f"Execution error for {output_file}:\n{output[:200]}...")
        elif language == "html":
            output = f"HTML execution skipped for {output_file}; validated by Tester"
            passed = True
            logger.debug(output)

        result = TestResult(test_code=test_code, passed=passed, output=output)
        self.save_output(task, result, status="tested")
        self.commit_changes(f"Executed {language} code for {output_file} for {task.task_id}")
        return "tested", result

    def start(self):
        logger.debug("Starting executor")

    def stop(self):
        logger.debug("Stopping executor")
