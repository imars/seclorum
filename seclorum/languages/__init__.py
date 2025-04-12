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
            "Create a 3D scene with a scrolling landscape using procedural terrain generation (PlaneGeometry with vertex heights via sin/random for mountains/valleys). "
            "Include at least 3 drones (BoxGeometry or similar), with the player controlling one using arrow keys (up/down for speed, left/right for lateral, W/S for vertical). "
            "Add 5 torus-shaped checkpoints, 10 box obstacles, a race timer, and win conditions (first to pass all checkpoints). "
            "Integrate with HTML UI (ids: myCanvas, timer, speed, standings, startButton) to update stats and handle start/reset. "
            "Use global THREE object from CDN (no require statements). "
            "Ensure camera follows the player drone. "
            "Return only the raw, executable JavaScript code, without tags, markup, comments, or explanations."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following JavaScript code:\n{code}\n\n"
            "Generate Jest test code to validate: "
            "1. Scene, camera, renderer initialization. "
            "2. Drones array (>= 3 drones). "
            "3. Procedural terrain (PlaneGeometry with modified vertices). "
            "4. Checkpoints (>= 5). "
            "5. UI updates (timer, speed, standings). "
            "6. Start button triggering race. "
            "Use global variables (scene, camera, drones, terrain, checkpoints) and avoid require statements. "
            "Return only the raw, executable Jest test code."
        )

    def validate_code(self, code: str) -> bool:
        return bool(code.strip() and any(kw in code for kw in ["THREE.Scene", "THREE.Mesh", "PlaneGeometry"]))

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} to support a Three.js drone racing game. "
            "Include a canvas (id='myCanvas') and a UI div (id='uiPanel') with: "
            "- Race timer (id='timer'), drone speed (id='speed'), race standings (id='standings'), start/reset button (id='startButton'). "
            "Use inline CSS: dark background (#222), white text, semi-transparent UI panel (rgba(0,0,0,0.5)), green button (#4CAF50) with hover (#3e8e41). "
            "Include script tags for Three.js CDN (https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js) and drone_game.js. "
            "Return only the raw HTML content, without comments, explanations, or JavaScript code."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given the following HTML code:\n{code}\n\n"
            "Generate Jest test code to validate: "
            "1. Canvas (id='myCanvas'). "
            "2. UI elements (ids: timer, speed, standings, startButton). "
            "3. Three.js script tag. "
            "Return only the raw Jest test code."
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
