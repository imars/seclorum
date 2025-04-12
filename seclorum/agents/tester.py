# seclorum/agents/tester.py
import os
import subprocess
import tempfile
from seclorum.agents.base import Agent
from seclorum.models import Task, TestResult, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_CONFIG
from typing import Tuple, Optional
import logging

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Tester initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        self.log_update(f"Testing code for task: {task.description}")
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        # Get generated code from task parameters
        generator_key = f"Generator_{self.task_id}"
        debugger_key = f"Debugger_{self.task_id}"
        code_output = None
        if debugger_key in task.parameters:
            code_output = task.parameters[debugger_key].get("result")
        elif generator_key in task.parameters:
            code_output = task.parameters[generator_key].get("result")

        if not code_output or not code_output.code.strip():
            self.log_update("No valid code to test")
            return "tested", TestResult(test_code="", passed=False, output="No code provided")

        code = code_output.code
        tests = code_output.tests if code_output.tests else ""

        # Validate tests
        if tests and not (tests.startswith("describe(") or tests.startswith("test(")):
            self.log_update("Invalid test code detected, discarding")
            tests = ""

        # Generate tests if not provided
        if not tests and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code) + (
                " Return only the raw, executable Jest test code for Node.js, compatible with Three.js browser code, "
                "without Markdown, comments, instructions, or explanations. Ensure tests reference the code via global variables "
                "(e.g., scene, camera, drone) and avoid require statements."
                if language == "javascript" else ""
            )
            use_remote = task.parameters.get("use_remote", None)
            raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False)
            tests = re.sub(r'```(?:javascript|python|cpp)?\n|\n```|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid|mock|recommended)[^\n]*?\n?', '', raw_tests).strip()
            if not tests.startswith("describe(") and not tests.startswith("test("):
                tests = ""
            self.log_update(f"Generated tests:\n{tests}")

        # Save and run tests
        output = "No tests executed"
        passed = False
        test_code = tests
        if tests:
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = os.path.join(tmpdir, "drone_game.test.js")
                with open(test_file, "w") as f:
                    f.write(tests)

                code_file = os.path.join(tmpdir, "drone_game.js")
                with open(code_file, "w") as f:
                    f.write(code)

                # Run Jest
                try:
                    result = subprocess.run(
                        ["npx", "jest", test_file, "--passWithNoTests"],
                        capture_output=True,
                        text=True,
                        cwd=tmpdir
                    )
                    output = result.stdout + result.stderr
                    passed = result.returncode == 0
                    self.log_update(f"Test execution output:\n{output}")
                except subprocess.CalledProcessError as e:
                    output = e.output
                    passed = False
                    self.log_update(f"Test execution failed:\n{output}")

        result = TestResult(test_code=test_code, passed=passed, output=output)
        self.save_output(task, result, status="tested")
        self.commit_changes(f"Tested {language} code for {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting tester")

    def stop(self):
        self.log_update("Stopping tester")
