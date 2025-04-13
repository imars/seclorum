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
            f"Generate JavaScript code for {output_file}. "
            "Create a Three.js game with drones racing across a 3D scrolling landscape with mountains, valleys, and obstacles. "
            "Include scene, camera, lighting, drone models, full controls (ArrowUp/Down/Left/Right, W/S), race mechanics (timer, checkpoints, win conditions), "
            "and UI updates (timer, speed, standings). Use global THREE object from CDN. "
            "Return only raw JavaScript code, no comments or markup."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given JavaScript code:\n{code}\n\n"
            "Generate Jest tests for scene, camera, drones, terrain, checkpoints, controls, and UI updates. "
            "Return only raw Jest test code, no comments."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and "THREE." in code and "scene" in code)

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file}. "
            "Include a canvas (id='myCanvas'), a UI div with timer, speed, standings (pre tag), and start/reset button. "
            "Use inline CSS: dark background, white Arial text, blue button with hover. Include Three.js CDN and drone_game.js. "
            "Return only raw HTML, no comments or JavaScript."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for canvas (id='myCanvas'), timer, speed, standings, and start/reset button. "
            "Return only raw Jest test code, no comments."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and "<canvas" in code and "id=\"myCanvas\"" in code and "<div" in code and "timer" in code and "<pre" in code)

class PythonHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        return "Python not implemented"

    def get_test_prompt(self, code: str) -> str:
        return "Python tests not implemented"

    def validate_code(self, code: str) -> bool:
        return False

LANGUAGE_HANDLERS: Dict[str, LanguageHandler] = {
    "javascript": JavaScriptHandler(),
    "html": HTMLHandler(),
    "python": PythonHandler()
}
