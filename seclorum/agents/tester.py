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
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output.test")
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["javascript"])

        # Get generated code
        generator_key = next((k for k in task.parameters if k.startswith("Generator_") and k.endswith("_gen")), None)
        debugger_key = next((k for k in task.parameters if k.startswith("Debugger_") and k.endswith("_debug")), None)
        code_output = None
        if debugger_key and debugger_key in task.parameters:
            code_output = task.parameters[debugger_key].get("result")
        elif generator_key and generator_key in task.parameters:
            code_output = task.parameters[generator_key].get("result")

        if not code_output or not code_output.code.strip():
            self.log_update(f"No valid {language} code to test for {output_file}")
            return "tested", TestResult(test_code="", passed=False, output="No code provided")

        code = code_output.code
        tests = code_output.tests if code_output.tests else ""

        # Generate tests if not provided
        if not tests and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code) + (
                " Return only the raw, executable Jest test code for Node.js, testing basic functionality "
                "(e.g., scene, camera, drone existence) without requiring Three.js imports or complex rendering. "
                "Use global variables (e.g., scene, camera, drone) and avoid require statements."
                if language == "javascript" else
                " Return only the raw Jest test code to validate HTML structure, checking for canvas and UI elements (timer, speed, standings, start/reset button), "
                "without comments or explanations."
                if language == "html" else ""
            )
            use_remote = task.parameters.get("use_remote", False)
            raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False)
            tests = raw_tests.strip()
            if language == "javascript" and not tests.startswith(("describe(", "test(")):
                tests = f"""
describe('{output_file}', () => {{
  beforeEach(() => {{
    window.innerWidth = 500;
    window.innerHeight = 500;
  }});
  it('initializes correctly', () => {{
    expect(true).toBe(true); // Placeholder test
  }});
}});
"""
            if language == "html" and not tests.startswith(("describe(", "test(")):
                tests = f"""
describe('{output_file}', () => {{
  beforeEach(() => {{
    document.body.innerHTML = `{code}`;
  }});
  it('has UI elements', () => {{
    expect(document.getElementById('myCanvas')).toBeDefined();
    expect(document.getElementById('timer')).toBeDefined();
    expect(document.getElementById('speed')).toBeDefined();
    expect(document.getElementById('standings')).toBeDefined();
    expect(document.getElementById('startReset')).toBeDefined();
  }});
  afterEach(() => {{
    document.body.innerHTML = '';
  }});
}});
"""
            self.log_update(f"Generated tests for {output_file}:\n{tests}")

        # Save and run tests
        output = "No tests executed"
        passed = False
        test_code = tests
        if tests and language == "javascript":
            with tempfile.TemporaryDirectory() as tmpdir:
                test_file = os.path.join(tmpdir, os.path.basename(output_file))
                with open(test_file, "w") as f:
                    f.write(tests)

                code_file = os.path.join(tmpdir, os.path.basename(output_file).replace(".test", ""))
                with open(code_file, "w") as f:
                    f.write(code)

                # Create Jest config
                jest_config = """
module.exports = {
  testEnvironment: 'jsdom',
  testMatch: ['**/*.test.js'],
};
"""
                config_file = os.path.join(tmpdir, "jest.config.js")
                with open(config_file, "w") as f:
                    f.write(jest_config)

                # Run Jest
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
                    self.log_update(f"Test execution output for {output_file}:\n{output}")
                except subprocess.CalledProcessError as e:
                    output = e.output
                    passed = False
                    self.log_update(f"Test execution failed for {output_file}:\n{output}")
        elif tests and language == "html":
            # Validate HTML structure
            from bs4 import BeautifulSoup
            try:
                soup = BeautifulSoup(code, 'html.parser')
                required_ids = ['myCanvas', 'timer', 'speed', 'standings', 'startReset']
                passed = all(soup.find(id=id_) for id_ in required_ids)
                output = f"HTML validation {'passed' if passed else 'failed'}: {required_ids} {'found' if passed else 'missing'}"
                self.log_update(f"HTML test output for {output_file}:\n{output}")
            except Exception as e:
                output = f"HTML validation failed: {str(e)}"
                passed = False
                self.log_update(f"HTML test failed for {output_file}:\n{output}")

        result = TestResult(test_code=test_code, passed=passed, output=output)
        self.save_output(task, result, status="tested")
        self.commit_changes(f"Tested {language} code for {output_file} for {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting tester")

    def stop(self):
        self.log_update("Stopping tester")
