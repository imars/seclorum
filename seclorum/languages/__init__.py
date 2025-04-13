# seclorum/languages/__init__.py
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
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file}. "
            "Create a Three.js drone racing game with a 3D scene. "
            "Include: "
            "- Scene, perspective camera, WebGL renderer (use canvas#myCanvas). "
            "- Drone (cube, red material) with controls: ArrowUp/Down (speed), ArrowLeft/Right (strafe), W/S (altitude). "
            "- Basic terrain (plane geometry, sin-based heightmap for mountains/valleys). "
            "- 2 AI drones (blue cubes) moving randomly. "
            "- 3 torus-shaped checkpoints (yellow). "
            "- UI updates: timer (id='timer'), speed (id='speed'), standings (id='standings'). "
            "Use global THREE from CDN. Return clean JavaScript code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Generating JavaScript test prompt")
        return (
            f"Given JavaScript code:\n{code}\n\n"
            "Generate Jest tests for Three.js drone game. "
            "Test scene initialization (scene, camera, renderer). "
            "Test drone controls (ArrowUp/Down/Left/Right, W/S). "
            "Test UI updates (timer, speed, standings). "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["THREE.", "scene", "camera", "renderer", "addEventListener"]
        valid = bool(code.strip() and all(kw in code for kw in required))
        logger.debug(f"JavaScript validation: {'valid' if valid else 'invalid'}, keywords={required}")
        return valid

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating HTML prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file}. "
            "Create: "
            "- Full-screen <canvas id='myCanvas'> for Three.js. "
            "- UI <div id='ui'> with: "
            "  - Timer (<span id='timer'>0</span>s). "
            "  - Speed (<span id='speed'>0</span>). "
            "  - Standings (<pre id='standings'>-</pre>). "
            "  - Button (<button id='startReset'>Start</button>). "
            "- Inline CSS: black background, white Arial text, UI top-left, button blue (#007bff) with hover (#0056b3). "
            "- Scripts: Three.js CDN (https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js), drone_game.js. "
            "Return clean HTML code, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Generating HTML test prompt")
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for drone game UI. "
            "Test canvas (id='myCanvas'). "
            "Test UI elements (id='timer', 'speed', 'standings', 'startReset'). "
            "Test script tags (Three.js CDN, drone_game.js). "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["<canvas", "<script", "three.min.js", "drone_game.js"]
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
