# seclorum/agents/executor.py
import subprocess
import os
import re
import tempfile
from typing import Tuple
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.languages import LANGUAGE_CONFIG

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.log_update(f"Executor initialized for task {task_id}")

    def clean_code(self, code: str) -> Tuple[str, bool]:
        """Extract code from <script> tags if present, return cleaned code and browser flag."""
        script_match = re.search(r'<\s*script[^>]*>(.*?)<\s*/\s*script\s*>', code, re.DOTALL)
        if script_match:
            cleaned = script_match.group(1).strip()
            self.log_update(f"Extracted code from <script> tags:\n{cleaned}")
            return cleaned, True
        return code.strip(), False

    def execute_with_jsdom(self, code: str, temp_file: str) -> Tuple[bool, str]:
        """Execute JavaScript code in a jsdom environment for browser-like context."""
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

// Execute the user code
try {
  const userCode = fs.readFileSync('{temp_file}', 'utf8');
  const scriptEl = document.createElement('script');
  scriptEl.textContent = userCode;
  document.body.appendChild(scriptEl);
  console.log('Execution completed');
} catch (e) {
  console.log('Error during execution:', e.message);
}

fs.writeFileSync('{temp_file}.out', consoleOutput);
process.exit(consoleOutput.includes('Error') ? 1 : 0);
""".format(temp_file=temp_file)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(jsdom_script)
            js_file_path = js_file.name

        try:
            self.log_update(f"Running jsdom script: node {js_file_path}")
            output = subprocess.check_output(["node", js_file_path], stderr=subprocess.STDOUT, text=True, timeout=10)
            output += open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else ""
            passed = "Error" not in output
        except subprocess.CalledProcessError as e:
            output = (e.output or "") + (open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else "")
            passed = False
        except subprocess.TimeoutExpired as e:
            output = (e.output.decode('utf-8') if e.output else "Timeout") + (open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else "")
            passed = False
        except Exception as e:
            output = str(e)
            passed = False
        finally:
            for file in [js_file_path, f"{temp_file}.out"]:
                if os.path.exists(file):
                    os.remove(file)

        return passed, output

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        self.log_update(f"Executing task {task.task_id}")
        generator_key = next((key for key in task.parameters if key.startswith("Generator_")), None)
        generator_output = task.parameters.get(generator_key, {}).get("result") if generator_key else None
        tester_key = next((key for key in task.parameters if key.startswith("Tester_")), None)
        tester_output = task.parameters.get(tester_key, {}).get("result") if tester_key else None
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        if not generator_output or not isinstance(generator_output, CodeOutput):
            self.log_update("No valid code from generator")
            result = TestResult(test_code="", passed=False, output="No code provided")
            self.store_output(task, "tested", result)
            return "tested", result

        code_output = generator_output
        self.log_update(f"Executing code:\n{code_output.code}")

        test_result = tester_output if tester_output and isinstance(tester_output, TestResult) else TestResult(test_code="", passed=False)
        clean_code, is_browser_code = self.clean_code(code_output.code)
        full_code = f"{clean_code}\n\n{self.clean_code(test_result.test_code)[0]}" if test_result.test_code else clean_code

        if not full_code.strip():
            self.log_update("No code to execute after cleaning")
            result = TestResult(test_code=test_result.test_code, passed=False, output="No executable code after cleaning")
            self.store_output(task, "tested", result)
            return "tested", result

        with tempfile.NamedTemporaryFile(mode='w', suffix=config['file_extension'], delete=False) as temp_file:
            temp_file.write(full_code)
            temp_file_path = temp_file.name

        try:
            if language == "javascript":
                if test_result.test_code:
                    cmd = ["npx", "jest", temp_file_path, "--silent"]
                    self.log_update(f"Running test command: {' '.join(cmd)}")
                    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
                    passed = True
                elif is_browser_code or "window" in full_code or "document" in full_code:  # Generic browser hints
                    self.log_update("Detected browser-oriented code, using jsdom")
                    passed, output = self.execute_with_jsdom(full_code, temp_file_path)
                else:
                    cmd = ["node", temp_file_path]
                    self.log_update(f"Running command: {' '.join(cmd)}")
                    output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
                    passed = True
            elif language == "python":
                cmd = ["python", "-B", temp_file_path]
                self.log_update(f"Running command: {' '.join(cmd)}")
                output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
                passed = True
            else:
                self.log_update(f"Unsupported language: {language}")
                result = TestResult(test_code=test_result.test_code, passed=False, output=f"Language {language} not supported")
                self.store_output(task, "tested", result)
                return "tested", result

            self.log_update(f"Execution output: {output}")
        except subprocess.CalledProcessError as e:
            self.log_update(f"Execution failed with error: {e.output}")
            output = e.output
            passed = False
        except subprocess.TimeoutExpired as e:
            self.log_update(f"Execution timed out: {e.output}")
            output = e.output.decode('utf-8') if e.output else "Timeout"
            passed = False
        except Exception as e:
            self.log_update(f"Unexpected execution error: {str(e)}")
            output = str(e)
            passed = False
        finally:
            if os.path.exists(temp_file_path):
                self.log_update(f"Cleaning up {temp_file_path}")
                os.remove(temp_file_path)

        result = TestResult(test_code=test_result.test_code, passed=passed, output=output)
        self.log_update(f"Final result: passed={result.passed}, output={result.output}")
        self.store_output(task, "tested", result)
        self.commit_changes(f"Executed {language} code for task {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting executor")

    def stop(self):
        self.log_update("Stopping executor")
