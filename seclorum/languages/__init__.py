# seclorum/languages/__init__.py
from abc import ABC, abstractmethod
from typing import Dict, Optional
from seclorum.models import Task
import logging

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
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file}. "
            "Create a Three.js drone racing game with a dynamic 3D scene. "
            "Include a scrolling landscape with mountains (sin-based heightmaps), valleys, flatlands, and obstacles (boxes/trees). "
            "Add a scene, perspective camera, ambient/directional lighting, and textured drone models (cubes or GLTF if simple). "
            "Implement player controls: ArrowUp/Down (speed), ArrowLeft/Right (strafe), W/S (altitude). "
            "Add 2-3 AI drones with pathfinding to follow checkpoints. "
            "Include race mechanics: timer, 5+ torus-shaped checkpoints, collision detection, win condition (all checkpoints). "
            "Add obstacles (avoidable boxes) and UI integration (update timer, speed, standings via DOM). "
            "Use global THREE from CDN (no require). Return clean JavaScript code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given JavaScript code:\n{code}\n\n"
            "Generate Jest tests for Three.js drone game. "
            "Test scene initialization (scene, camera, renderer). "
            "Test drone controls (ArrowUp/Down/Left/Right, W/S). "
            "Test AI drone movement (pathfinding to checkpoints). "
            "Test race mechanics (timer, checkpoints, win condition). "
            "Test UI updates (timer, speed, standings). "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["THREE.", "scene", "camera", "renderer", "addEventListener"]
        return bool(code.strip() and all(kw in code for kw in required))

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file}. "
            "Create a full-screen <canvas id='myCanvas'> for Three.js rendering. "
            "Add a UI <div id='ui'> with: "
            "- Timer (<span id='timer'>0</span>s), "
            "- Speed (<span id='speed'>0</span>), "
            "- Standings (<pre id='standings'>-</pre>), "
            "- Start/Reset button (<button id='startReset'>Start</button>). "
            "Use inline CSS: black background, white Arial text, UI at top-left, button blue (#007bff) with hover (#0056b3). "
            "Include Three.js CDN (<script src='https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js'>). "
            "Include <script src='drone_game.js'> after Three.js. "
            "Return clean HTML code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for drone game UI. "
            "Test canvas (id='myCanvas'). "
            "Test UI elements (id='timer', 'speed', 'standings', 'startReset'). "
            "Test script tags (Three.js CDN, drone_game.js). "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["<canvas", "id=\"myCanvas\"", "<script", "three.min.js", "drone_game.js"]
        return bool(code.strip() and all(kw in code for kw in required))

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
