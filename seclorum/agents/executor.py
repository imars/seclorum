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
""".format(temp_file=temp_file)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as js_file:
            js_file.write(jsdom_script)
            js_file_path = js_file.name

        try:
            self.log_update(f"Running jsdom script: node {js_file_path}")
            subprocess.check_call(["node", js_file_path], timeout=10)
            output = open(f"{temp_file}.out", "r").read() if os.path.exists(f"{temp_file}.out") else "No output captured"
            passed = True
        except subprocess.CalledProcessError as
