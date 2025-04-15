from abc import ABC, abstractmethod
from typing import Dict, Optional
from seclorum.models import Task
import logging
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LanguageHandler(ABC):
    @abstractmethod
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        pass

    @abstractmethod
    def get_test_prompt(self, code: str) -> str:
        pass

    @abstractmethod
    def validate_code(self, code: str) -> bool:
        pass

class JavaScriptHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating JavaScript prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file} based on the task description. "
            "Return clean JavaScript code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Generating JavaScript test prompt")
        return (
            f"Given JavaScript code:\n{code}\n\n"
            "Generate Jest tests for the code. "
            "Test core functionality and key behaviors. "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        valid = bool(code.strip())
        logger.debug(f"JavaScript validation: {'valid' if valid else 'invalid'}, code_length={len(code)}")
        return valid

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating HTML prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} based on the task description. "
            "Include necessary UI elements and scripts. "
            "Return clean HTML code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Generating HTML test prompt")
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for the HTML structure. "
            "Test key elements and scripts. "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["<html", "<body"]
        valid = bool(code.strip() and all(kw in code for kw in required))
        logger.debug(f"HTML validation: {'valid' if valid else 'invalid'}, keywords={required}")
        return valid

class PythonHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        logger.debug("Python code prompt requested, not implemented")
        return "Python not implemented"

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Python test prompt requested, not implemented")
        return "Python tests not implemented"

    def validate_code(self, code: str) -> bool:
        logger.debug("Python code validation requested, not implemented")
        return False

LANGUAGE_HANDLERS: Dict[str, LanguageHandler] = {
    "javascript": JavaScriptHandler(),
    "html": HTMLHandler(),
    "python": PythonHandler()
}
