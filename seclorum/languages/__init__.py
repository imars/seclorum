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
            f"Generate JavaScript code for {output_file} to create a Three.js drone racing game. "
            "Include a 3D scene with a scrolling landscape of mountains, valleys, and obstacles using procedural terrain generation. "
            "Add multiple drones (at least 3) controlled by arrow keys (up/down/left/right) and W/S for vertical movement. "
            "Implement race mechanics with a timer, checkpoints (torus-shaped), and win conditions (first to pass all checkpoints). "
            "Integrate with HTML UI (ids: timer, speed, standings, startButton) to update race stats and handle start/reset. "
            "Use the global THREE object from a CDN, avoiding Node.js require statements. "
            "Return only the raw, executable JavaScript code, without tags, markup, comments, or explanations."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following JavaScript code:\n{code}\n\n"
            "Generate Jest test code to validate the scene, camera, renderer, drones (array length >= 3), terrain (procedural), checkpoints (>= 3), "
            "and UI interactions (timer, speed, standings updates). "
            "Use global variables (e.g., scene, camera, drones) and avoid require statements. "
            "Return only the raw, executable Jest test code, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and ("THREE.Scene" in code or "THREE.Mesh" in code))

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} to support a Three.js drone racing game. "
            "Include a canvas (id='myCanvas') and a UI div (id='uiPanel') with elements for race timer (id='timer'), "
            "drone speed (id='speed'), race standings (id='standings'), and a start/reset button (id='startButton'). "
            "Use inline CSS for a dark background (#222), white text, semi-transparent UI panel (rgba(0,0,0,0.5)), "
            "and a green button (#4CAF50) with hover effect (#3e8e41). "
            "Include script tags for Three.js CDN (https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js) and drone_game.js. "
            "Return only the raw HTML content, without comments, explanations, or JavaScript code."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following HTML code:\n{code}\n\n"
            "Generate Jest test code to validate the presence of a canvas (id='myCanvas'), UI elements (ids: timer, speed, standings, startButton), "
            "and Three.js script tag. "
            "Return only the raw Jest test code, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and "myCanvas" in code and "uiPanel" in code and "three.js" in code)

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
