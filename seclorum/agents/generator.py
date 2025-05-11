# seclorum/agents/generator.py
from typing import Tuple, Any, Dict, Optional
from seclorum.agents.agent import Agent
from seclorum.models import Task, CodeOutput
from seclorum.languages import LANGUAGE_HANDLERS
import logging
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Generator(Agent):
    def __init__(self, name: str, session_id: str, model_manager=None):
        super().__init__(name, session_id, model_manager)
        logger.debug(f"Generator initialized: name={name}, session_id={session_id}")

    def get_prompt(self, task: Task) -> str:
        """Generate a prompt for code generation."""
        language = task.parameters.get("language", "javascript").lower()
        output_files = task.parameters.get("output_files", ["app.js"])
        handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
        system_prompt = (
            "You are a coding assistant that generates valid code for a web-based application. "
            "Output ONLY the code, with no comments, no markdown, no code block markers (```), "
            "and no text outside the code itself."
        )
        user_prompt = handler.get_code_prompt(task, output_files[0])
        if self.model_manager.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        return (
            f"<|start_header_id|>system<|end_header_id>\n\n{system_prompt}<|eot_id>\n"
            f"<|start_header_id|>user<|end_header_id>\n\n{user_prompt}<|eot_id>\n"
            f"<|start_header_id|>assistant<|end_header_id>\n\n"
        )

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate a retry prompt for failed code generation."""
        language = self.task.parameters.get("language", "javascript").lower() if hasattr(self, 'task') else "javascript"
        handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            issues.append("Generated code is invalid or does not meet language-specific requirements")
        feedback = "\n".join([f"- {issue}" for issue in issues]) or "Output did not meet requirements"
        guidance = (
            f"Output ONLY valid {language} code, with no comments, no markdown, no code block markers (```), "
            "and no text outside the code itself. Ensure the code is syntactically correct and functional."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return schema for code output."""
        return {
            "type": "string",
            "description": "Valid code in the specified language"
        }

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"Processing task {task.task_id}: language={task.parameters.get('language', '')}, "
                    f"output_files={task.parameters.get('output_files', [task.parameters.get('output_file')])}")
        try:
            language = task.parameters.get("language", "javascript").lower()
            if language not in LANGUAGE_HANDLERS:
                logger.error(f"Unsupported language: {language}")
                return "failed", CodeOutput(code="", tests=None)

            handler = LANGUAGE_HANDLERS[language]
            output_files = task.parameters.get("output_files", [task.parameters.get("output_file", "app.js")])
            if not isinstance(output_files, list):
                output_files = [output_files]

            results = {}
            for output_file in output_files:
                logger.debug(f"Generating code for {output_file}")
                code = self.generate_code(task, handler, output_file)
                if not code or not handler.validate_code(code):
                    logger.warning(f"Generated code invalid for {output_file}, using fallback")
                    code = handler.get_fallback_code(task)
                results[output_file] = code

            primary_file = task.parameters.get("output_file", output_files[0])
            primary_code = results.get(primary_file, "")
            test_code = None
            if task.parameters.get("generate_tests", False):
                test_code = handler.get_test_prompt(primary_code) or "// Default test\nexpect(true).toBe(true);"

            logger.debug(f"Generated code for {primary_file}: length={len(primary_code)}")
            return "generated", CodeOutput(
                code=primary_code,
                tests=test_code,
                additional_files={k: v for k, v in results.items() if k != primary_file},
                output_files=output_files
            )
        except Exception as e:
            logger.error(f"Error generating code for task {task.task_id}: {str(e)}")
            return "failed", CodeOutput(code="", tests=None)

    def generate_code(self, task: Task, handler, output_file: str) -> str:
        logger.debug(f"Inferring code for task={task.task_id}, output_file={output_file}")
        try:
            code = self.infer(
                prompt=self.get_prompt(task),
                task=task,
                use_remote=task.parameters.get("use_remote", False),
                use_context=True,
                max_tokens=4096,
                function_call={"schema": self.get_schema()}
            )
            code = re.sub(r'^```[\w\s]*\n|```$', '', code, flags=re.MULTILINE)
            code = re.sub(r'^\s*//.*?$|^\s*#.*?$|/\*[\s\S]*?\*/', '', code, flags=re.MULTILINE)
            code = code.strip()
            logger.debug(f"Raw generated code for {output_file}: {code[:100]}...")
            return code
        except Exception as e:
            logger.error(f"Inference failed for {output_file}: {str(e)}")
            return ""
