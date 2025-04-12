# seclorum/agents/tester.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.languages import LANGUAGE_CONFIG
import subprocess
import os
import tempfile
import logging

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.log_update(f"Tester initialized for Task {self.task_id}")

    def process_task(self, task: Task) -> tuple[str, TestResult]:
        self.log_update(f"Testing for Task {self.task_id}")
        generator_output = task.parameters.get("Generator_dev_task", {}).get("result")

        if not generator_output or not isinstance(generator_output, CodeOutput):
            self.log_update("No valid code from Generator")
            return "tested", TestResult(test_code="", passed=False, output="No code provided")

        code_output = generator_output
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        test_code = code_output.tests or ""
        if not test_code and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code_output.code)
            test_code = self.model.generate(test_prompt).strip()
            test_code = test_code.replace(f"```{language}", "").replace("```", "").strip()
            self.log_update(f"Generated {language} test code:\n{test_code}")

        # Initialize test result
        result = TestResult(test_code=test_code, passed=False, output="")

        # Run tests for JavaScript using Puppeteer
        if language == "javascript" and code_output.code.strip():
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    # Write code to temporary file
                    code_path = os.path.join(tmpdir, "test.js")
                    with open(code_path, "w") as f:
                        f.write(code_output.code)

                    # Run Puppeteer
                    puppeteer_script = "seclorum/scripts/run_puppeteer.js"
                    proc = subprocess.run(
                        ["node", puppeteer_script, code_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    output_path = f"{code_path}.out"
                    if os.path.exists(output_path):
                        with open(output_path, "r") as f:
                            test_output = f.read()
                    else:
                        test_output = proc.stdout + proc.stderr

                    self.log_update(f"Puppeteer output:\n{test_output}")
                    result.output = test_output
                    result.passed = proc.returncode == 0 and "Execution successful" in test_output
            except subprocess.TimeoutExpired:
                result.output = "Test execution timed out"
                self.log_update(result.output)
            except Exception as e:
                result.output = f"Test execution failed: {str(e)}"
                self.log_update(result.output)

        self.store_output(task, "tested", result)
        self.commit_changes(f"Tested {language} code for Task {self.task_id}")
        return "tested", result
