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
            "Implement a Three.js game with: "
            "- A procedural 3D scrolling terrain with mountains, valleys, and obstacles using vertex manipulation. "
            "- Multiple drones (at least 3) with full controls (ArrowUp/Down/Left/Right for speed and direction, W/S for altitude). "
            "- Race mechanics including a timer, 5+ checkpoints (torus shapes), collision detection, and win conditions. "
            "- Dynamic camera following the lead drone. "
            "- UI integration updating HTML elements (timer, speed, standings). "
            "Use the global THREE object from a CDN, avoiding Node.js require statements. "
            "Return only the raw, executable JavaScript code, without tags, markup, comments, or explanations."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following JavaScript code:\n{code}\n\n"
            "Generate Jest test code to validate: "
            "- Scene, camera, renderer, and drones initialization. "
            "- Terrain with non-flat geometry (check vertex heights). "
            "- Checkpoints (at least 5) and collision detection. "
            "- UI updates (timer, speed, standings). "
            "- Key controls (Arrow keys, W/S). "
            "Return only the raw, executable Jest test code for Node.js, using global variables, "
            "avoiding require statements, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        return bool(
            code.strip() and
            "THREE." in code and
            "PlaneGeometry" in code and
            "Mesh" in code and
            "addEventListener('keydown'" in code and
            not code.lower().startswith(("error", "invalid"))
        )

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} based on the plan. "
            "Include: "
            "- A canvas with id='myCanvas'. "
            "- A styled UI div with elements for race timer (id='timer'), drone speed (id='speed'), race standings (id='standings'), and a start/reset button (id='startButton'). "
            "- Inline CSS for a dark background, white text, semi-transparent UI panel, and a styled button with hover effect. "
            "- Script tags to load Three.js CDN and drone_game.js. "
            "Return only the raw HTML content, without comments, explanations, or JavaScript code."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following HTML code:\n{code}\n\n"
            "Generate Jest test code to validate the presence of: "
            "- Canvas (id='myCanvas'). "
            "- UI elements (id='timer', 'speed', 'standings', 'startButton'). "
            "- Three.js script tag. "
            "Return only the raw Jest test code, without comments or explanations."
        )

    def validate_code(self, code: str) -> bool:
        return bool(
            code.strip() and
            "<canvas" in code and
            "id=\"myCanvas\"" in code and
            "id=\"timer\"" in code and
            "id=\"speed\"" in code and
            "id=\"standings\"" in code and
            "id=\"startButton\"" in code and
            "<script" in code
        )

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
