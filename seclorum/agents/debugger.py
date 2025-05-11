# seclorum/agents/debugger.py
from typing import Tuple, Any, Dict, Optional
from seclorum.agents.agent import Agent
from seclorum.models import Task, CodeOutput
from seclorum.languages import LANGUAGE_HANDLERS
import logging
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Debugger(Agent):
    def __init__(self, name: str, session_id: str, model_manager=None):
        super().__init__(name, session_id, model_manager)
        logger.debug(f"Debugger initialized: name={name}, session_id={session_id}")

    def get_prompt(self, task: Task) -> str:
        """Generate prompt for debugging code based on test failures."""
        language = task.parameters.get("language", "javascript").lower()
        code = task.parameters.get("code", "")
        test_output = task.parameters.get("test_output", "No test output available")
        output_file = task.parameters.get("output_file", "unknown")
        system_prompt = (
            "You are a coding assistant that debugs code based on test failures. "
            "Output ONLY valid corrected code in the specified language, no comments, no markdown, "
            "no code block markers (```), and no text outside the code. "
            "Fix issues identified in the test output while preserving the original functionality."
        )
        user_prompt = (
            f"Language: {language}\n"
            f"Source file: {output_file}\n"
            f"Original code:\n{code}\n\n"
            f"Test output:\n{test_output}\n\n"
            f"Fix the code to address the issues identified in the test output. "
            f"Ensure the corrected code is syntactically correct and maintains the intended functionality."
        )
        if self.model_manager.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        return (
            f"<|start_header_id|>system<|end_header_id>\n{system_prompt}\n"
            f"<|start_header_id|>user<|end_header_id>\n{user_prompt}"
        )

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate retry prompt for failed debug attempts."""
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            issues.append("Invalid code: must be syntactically correct and fix test failures")
        feedback = "\n".join([f"- {issue}" for issue in issues]) or "Code did not meet requirements"
        guidance = (
            "Output ONLY valid corrected code in the specified language, no comments, no markdown, "
            "no code block markers (```), and no text outside the code. "
            "Ensure the code fixes the test failures and maintains the original functionality."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return schema for debugged code output."""
        return {
            "type": "string",
            "description": "Corrected code that fixes test failures"
        }

    def strip_markdown_code(self, text: str) -> str:
        """Strip Markdown code fences from debugged code output."""
        return re.sub(r'```(?:\w+)?\n([\s\S]*?)\n```', r'\1', text).strip()

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"Processing task {task.task_id}: language={task.parameters.get('language', '')}")
        try:
            language = task.parameters.get("language", "javascript").lower()
            if language not in LANGUAGE_HANDLERS:
                logger.error(f"Unsupported language: {language}")
                return "failed", CodeOutput(code="", tests=None)

            handler = LANGUAGE_HANDLERS[language]
            code = task.parameters.get("code", "")
            test_output = task.parameters.get("test_output", "No test output available")
            if not code:
                logger.warning("No code provided for debugging")
                return "failed", CodeOutput(code="", tests=None)

            prompt = self.get_prompt(task)
            try:
                debugged_code = self.infer(
                    prompt=prompt,
                    task=task,
                    use_remote=task.parameters.get("use_remote", False),
                    max_tokens=4096,
                    function_call={"schema": self.get_schema()}
                )
                debugged_code = self.strip_markdown_code(debugged_code)
            except Exception as e:
                logger.error(f"Debug code inference failed: {str(e)}")
                debugged_code = code  # Fallback to original code

            if not debugged_code or not handler.validate_code(debugged_code):
                logger.warning("Invalid debugged code, returning original code")
                debugged_code = code

            logger.debug(f"Debugged code: {debugged_code[:100]}...")
            return "debugged", CodeOutput(
                code=debugged_code,
                tests=task.parameters.get("tests", None),
                additional_files=task.parameters.get("additional_files", {})
            )
        except Exception as e:
            logger.error(f"Error debugging task {task.task_id}: {str(e)}")
            return "failed", CodeOutput(code=code, tests=None)
