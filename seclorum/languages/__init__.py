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
            "Create a Three.js game with drones racing across a 3D scrolling landscape with mountains, valleys, obstacles. "
            "Include scene, camera, lighting, drone models. Add controls (ArrowUp/Down/Left/Right, W/S), "
            "race mechanics (timer, checkpoints, win conditions), UI updates (timer, speed, standings). "
            "Use global THREE from CDN, no require. Return raw JavaScript, no comments."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given JavaScript code:\n{code}\n\n"
            "Generate Jest tests for scene, camera, renderer, drones, terrain, checkpoints, controls, UI. "
            "Return raw Jest code, no comments."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and "THREE." in code and "scene" in code)

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file}. "
            "Include <canvas id='myCanvas'> and <div> with race timer, drone speed, standings, start/reset button. "
            "Use inline CSS: black background, white text, Arial, blue button with hover (#0056b3). "
            "Add Three.js CDN (<script src='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js'>) and <script src='drone_game.js'>. "
            "Return raw HTML, no comments."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for canvas (id='myCanvas'), UI elements (timer, speed, standings, startReset). "
            "Return raw Jest code, no comments."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and "<canvas" in code and "id=\"myCanvas\"" in code)

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
