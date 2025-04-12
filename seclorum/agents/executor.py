# seclorum/agents/executor.py
import os
import subprocess
import tempfile
from typing import Tuple, Optional
from seclorum.agents.base import Agent
from seclorum.models import Task, TestResult, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
import logging

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: Optional[ModelManager] = None):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Executor initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        self.log_update(f"Executing code for task: {task.description}")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", None)
        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            self.log_update(f"Unsupported language: {language}")
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
            self.log_update("No valid code to execute")
            return "tested", TestResult(test_code=test_code, passed=False, output="No code provided")

        code = code_output.code
        self.log_update(f"Executing code:\n{code}")

        output = "No execution performed"
        passed = False
        if language == "javascript" and test_code:
            with tempfile.TemporaryDirectory() as tmpdir:
                code_file = os.path.join(tmpdir, "code.js")
                with open(code_file, "w") as f:
                    f.write(code)

                test_file = os.path.join(tmpdir, "test.js")
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
                    self.log_update(f"Execution output:\n{output}")
                except subprocess.CalledProcessError as e:
                    output = e.output
                    passed = False
                    self.log_update(f"Unexpected execution error:\n{output}")
        elif language == "html":
            output = "HTML execution skipped, validated by Tester"
            passed = True  # Rely on Tester's validation
            self.log_update(output)

        result = TestResult(test_code=test_code, passed=passed, output=output)
        self.save_output(task, result, status="tested")
        self.commit_changes(f"Executed {language} code for {output_file or 'task'} for {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting executor")

    def stop(self):
        self.log_update("Stopping executor")
