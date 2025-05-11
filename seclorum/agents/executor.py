# seclorum/agents/executor.py
import os
import subprocess
import tempfile
import asyncio
from typing import Tuple, Optional, Dict, Any
from seclorum.agents.agent import Agent
from seclorum.models import Task, TestResult
from seclorum.languages import LANGUAGE_HANDLERS
from playwright.async_api import async_playwright, Playwright
import logging
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager=None):
        super().__init__(f"Executor_{task_id}", session_id, model_manager)
        self.task_id = task_id
        self.model_manager = model_manager  # Use provided model_manager, no default local model
        logger.debug(f"Executor initialized for Task {task_id}")

    def get_prompt(self, task: Task) -> str:
        """Generate prompt for validating execution environment (if needed)."""
        language = task.parameters.get("language", "javascript").lower()
        code = task.parameters.get("code", "")
        output_file = task.parameters.get("output_file", "unknown")
        system_prompt = (
            "You are a coding assistant that validates the execution environment for code. "
            "Output ONLY a string indicating environment readiness (e.g., 'Browser ready with Three.js' for JavaScript), "
            "no comments, no markdown, no code block markers (```), and no text outside the string."
        )
        user_prompt = (
            f"Language: {language}\n"
            f"Source file: {output_file}\n"
            f"Source code:\n{code[:500]}\n\n"
            f"Verify the execution environment for the source code. "
            f"For JavaScript, confirm a browser environment with Three.js is available. "
            f"For Python, confirm Python runtime availability. "
            f"Return a string describing the environment status."
        )
        if self.model_manager and self.model_manager.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        return (
            f"<|start_header_id|>system<|end_header_id>\n{system_prompt}\n"
            f"<|start_header_id|>user<|end_header_id>\n{user_prompt}"
        )

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate retry prompt for failed environment validation."""
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            issues.append("Invalid environment validation: must confirm execution environment readiness")
        feedback = "\n".join([f"- {issue}" for issue in issues]) or "Validation did not meet requirements"
        guidance = (
            "Output ONLY a string indicating environment readiness, no comments, no markdown, "
            "no code block markers (```), and no text outside the string."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return schema for environment validation output."""
        return {
            "type": "string",
            "description": "String indicating execution environment readiness"
        }

    def strip_markdown_code(self, text: str) -> str:
        """Strip Markdown code fences from output."""
        return re.sub(r'```(?:\w+)?\n([\s\S]*?)\n```', r'\1', text).strip()

    async def execute_javascript(self, code: str, test_code: str, output_file: str) -> Tuple[bool, str]:
        """Execute JavaScript code in a browser environment with Three.js."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            console_output = []
            errors = []

            def on_console(msg):
                console_output.append(f"{msg.type}: {msg.text}")

            def on_error(error):
                errors.append(f"Error: {error}")

            page.on("console", on_console)
            page.on("pageerror", on_error)

            try:
                # Create HTML with Three.js and code
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
                </head>
                <body>
                    <div id="app"><span id="count">0</span><button id="increment">Increment</button></div>
                    <script>
                    {code}
                    </script>
                    <script>
                    {test_code}
                    </script>
                </body>
                </html>
                """
                html_file = os.path.join(tempfile.gettempdir(), f"{self.task_id}_{output_file}.html")
                with open(html_file, "w") as f:
                    f.write(html_content)

                await page.goto(f"file://{html_file}")
                await page.wait_for_timeout(1000)  # Allow scripts to run

                passed = len(errors) == 0
                output = "\n".join(console_output + errors)
                if not output:
                    output = "No console output or errors captured"
                logger.debug(f"JavaScript execution output for {output_file}:\n{output[:200]}...")
                return passed, output
            except Exception as e:
                logger.error(f"JavaScript execution error for {output_file}: {str(e)}")
                return False, f"Execution error: {str(e)}"
            finally:
                await browser.close()

    def execute_python(self, code: str, test_code: str, output_file: str) -> Tuple[bool, str]:
        """Execute Python code (placeholder for future implementation)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            code_file = os.path.join(tmpdir, f"{os.path.basename(output_file)}.py")
            with open(code_file, "w") as f:
                f.write(code + "\n" + test_code)
            try:
                result = subprocess.run(
                    ["python", code_file],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
                    env={**os.environ, "TOKENIZERS_PARALLELISM": "false"}
                )
                output = result.stdout + result.stderr
                passed = result.returncode == 0
                logger.debug(f"Python execution output for {output_file}:\n{output[:200]}...")
                return passed, output
            except subprocess.CalledProcessError as e:
                logger.error(f"Python execution error for {output_file}:\n{e.output[:200]}...")
                return False, e.output

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        logger.debug(f"Executing code for task: {task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", f"temp_{language}")
        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            return "tested", TestResult(test_code="", passed=False, output=f"Language {language} not supported")

        # Check for Generator or Tester output
        code_output = None
        test_code = ""
        for key, value in task.parameters.items():
            if isinstance(value, dict) and value.get("status") in ["generated", "tested"]:
                if key.startswith("Generator_") and value.get("result"):
                    code_output = value["result"]
                elif key.startswith("Tester_") and value.get("result"):
                    test_result = value["result"]
                    if isinstance(test_result, TestResult):
                        test_code = test_result.test_code

        if not code_output or not code_output.code.strip():
            logger.warning(f"No valid code to execute for {output_file}")
            return "tested", TestResult(test_code=test_code, passed=False, output="No code provided")

        code = code_output.code
        logger.debug(f"Executing code for {output_file}:\n{code[:200]}...")

        output = "No execution performed"
        passed = False
        if language == "javascript":
            # Run JavaScript in browser with Playwright
            loop = asyncio.get_event_loop()
            passed, output = loop.run_until_complete(self.execute_javascript(code, test_code, output_file))
        elif language == "html":
            output = f"HTML execution skipped for {output_file}; validated by Tester"
            passed = handler.validate_code(code)
            logger.debug(output)
        elif language == "css":
            output = f"CSS execution skipped for {output_file}; validated by Tester"
            passed = handler.validate_code(code)
            logger.debug(output)
        elif language == "json":
            output = f"JSON execution skipped for {output_file}; validated by Tester"
            passed = handler.validate_code(code)
            logger.debug(output)
        elif language == "python":
            # Placeholder for Python execution
            passed, output = self.execute_python(code, test_code, output_file)
        else:
            output = f"Execution not supported for {language}"
            logger.debug(output)

        # Store output for Debugger
        task.parameters["execution_output"] = output
        result = TestResult(test_code=test_code, passed=passed, output=output)
        self.save_output(task, result, status="tested")
        self.commit_changes(f"Executed {language} code for {output_file} for {task.task_id}")
        return "tested", result

    def start(self):
        logger.debug("Starting executor")

    def stop(self):
        logger.debug("Stopping executor")
