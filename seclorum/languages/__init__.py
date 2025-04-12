# seclorum/languages/__init__.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from seclorum.models import Task

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
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file} based on the plan. "
            "Focus on game logic, Three.js scene, drone controls, and race mechanics. "
            "Return only the raw, executable JavaScript code suitable for browser environments using the global THREE object from a CDN, "
            "avoiding Node.js require statements, without tags, markup, comments, or explanations."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following JavaScript code:\n{code}\n\n"
            "Generate Jest test code to validate the scene, camera, renderer, drones, terrain, checkpoints, and UI interactions. "
            "Return only the raw, executable Jest test code for Node.js, using global variables (e.g., scene, camera, drone) "
            "and avoiding require statements, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        # Basic syntax check for JavaScript
        return bool(code.strip() and "THREE." in code and not code.lower().startswith(("error", "invalid")))

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} based on the plan. "
            "Include a canvas with id='myCanvas' and a styled UI div with elements for race timer, drone speed, race standings, and a start/reset button. "
            "Use inline CSS for a dark background, white text, and button styling. "
            "Return only the raw HTML content, without comments, explanations, or JavaScript code."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following HTML code:\n{code}\n\n"
            "Generate Jest test code to validate the presence of a canvas (id='myCanvas') and UI elements (timer, speed, standings, start/reset button). "
            "Return only the raw Jest test code, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        # Check for essential HTML elements
        return bool(code.strip() and "<canvas" in code and "id=\"myCanvas\"" in code and "<div" in code)

class PythonHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        return "Python not yet implemented"

    def get_test_prompt(self, code: str) -> str:
        return "Python tests not yet implemented"

    def validate_code(self, code: str) -> bool:
        return False

LANGUAGE_HANDLERS: Dict[str, LanguageHandler] = {
    "javascript": JavaScriptHandler(),
    "html": HTMLHandler(),
    "python": PythonHandler()
}
