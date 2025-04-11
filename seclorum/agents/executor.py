# seclorum/agents/executor.py
import subprocess
import os
import re
from typing import Tuple
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.languages import LANGUAGE_CONFIG
import tempfile

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.log_update(f"Executor initialized for Task {task_id}")

    def clean_code(self, code: str) -> Tuple[str, bool]:
        """Extract code from <script> tags if present, return cleaned code and browser flag."""
        script_match = re.search(r'<\s*script[^>]*>(.*?)<\s*/\s*script\s*>', code, re.DOTALL)
        if script_match:
            cleaned = script_match.group(1).strip()
            self.log_update(f"Extracted code from <script> tags:\n{cleaned}")
            return cleaned, True
        return code.strip(), False

    def execute_with_jsdom(self, code: str, temp_file: str) -> Tuple[bool, str]:
        """Execute JavaScript code in a jsdom environment."""
        # Create a Node.js script to run the code with jsdom
        jsdom_script = """
const { JSDOM } = require('jsdom');
const fs = require('fs');

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', { runScripts: 'dangerously' });
const window = dom.window;
const document = window.document;

// Capture console output
let consoleOutput = '';
const originalConsoleLog = console.log;
console.log = (...args) => {
  consoleOutput += args.join(' ') + '\\n';
  originalConsoleLog(...args);
};

// Load and execute the user code
const userCode = fs.readFileSync('{temp_file}', 'utf8');
const scriptEl = document.createElement('script');
scriptEl.textContent = userCode;
document.body.appendChild(scriptEl);

// Simulate some drone game interaction (e.g., check if scene is defined)
let passed = false;
try {
  if (typeof window.THREE !== 'undefined' || typeof window.add === 'function') {
    passed = true;
  }
  console.log('Execution result:', passed ? 'Success' : 'No expected functionality detected');
} catch (e) {
  console.log('Error during execution:', e.message);
  passed = false;
}

fs.writeFileSync('{temp_file}.out', consoleOutput);
process.exit(passed ? 0 : 1);
""".format(temp_file=temp_file)  # Inject temp_file path safely

        # Write the jsdom script to a temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(jsdom_script)
            js_file_path = js_file.name

        try:
            self.log_update(f"Running jsdom script: node {js_file_path}")
            subprocess.check_call(["node", js_file_path], timeout=10)
            output = open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else "No output captured"
            passed = True
        except subprocess.CalledProcessError as e:
            output = open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else e.output or "Execution failed"
            passed = False
        except subprocess.TimeoutExpired as e:
            output = e.output.decode('utf-8') if e.output else "Timeout"
            passed = False
        finally:
            if os.path.exists(js_file_path):
                os.remove(js_file_path)
            if os.path.exists(f"{temp_file}.out"):
                os.remove(f"{temp_file}.out")

        return passed, output

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        self.log_update(f"Executing for Task {task.task_id}")
        generator_output = task.parameters.get("Generator_dev_task", {}).get("result")
        tester_output = task.parameters.get("Tester_dev_task", {}).get("result")
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        if not generator_output or not isinstance(generator_output, CodeOutput):
            self.log_update("No valid code from Generator")
            result = TestResult(test_code="", passed=False, output="No code provided")
            self.memory.save(response=result, task_id=task.task_id)
            task.parameters["Executor_dev_task"] = {"status": "tested", "result": result}
            return "tested", result

        code_output = generator_output
        self.log_update(f"Executing code:\n{code_output.code}")

        test_result = tester_output if tester_output and isinstance(tester_output, TestResult) else TestResult(test_code="", passed=False)
        clean_code, is_browser_code = self.clean_code(code_output.code)
        full_code = f"{clean_code}\n\n{self.clean_code(test_result.test_code)[0]}" if test_result.test_code else clean_code

        if not full_code.strip():
            self.log_update("No code to execute after cleaning")
            result = TestResult(test_code=test_result.test_code, passed=False, output="No executable code after cleaning")
            self.memory.save(response=result, task_id=task.task_id)
            return "tested", result

        temp_file = f"temp_{self.task_id}{config['file_extension']}"
        self.log_update(f"Writing to {temp_file}")
        with open(temp_file, "w") as f:
            f.write(full_code)

        try:
            if language == "javascript":
                if test_result.test_code:
                    cmd = ["npx", "jest", temp_file, "--silent"]
                    self.log_update(f"Running Jest command: {' '.join(cmd)}")
                    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
                    passed = True
                elif is_browser_code or "THREE" in full_code:  # Detect Three.js or script tags
                    self.log_update("Detected browser-oriented code, using jsdom")
                    passed, output = self.execute_with_jsdom(full_code, temp_file)
                else:
                    cmd = ["node", temp_file]
                    self.log_update
