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

    @abstractmethod
    def get_code(self, task: Task, output_file: str) -> str:
        pass

    @abstractmethod
    def get_fallback_code(self, task: Task) -> str:
        pass

class JavaScriptHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating JavaScript prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file} based on the task description. "
            "Use global THREE object from CDN (no import statements). "
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
        valid = bool(code.strip()) and "import " not in code
        logger.debug(f"JavaScript validation: {'valid' if valid else 'invalid'}, code_length={len(code)}")
        return valid

    def get_code(self, task: Task, output_file: str) -> str:
        logger.debug(f"Generating JavaScript code for task={task.task_id}, output_file={output_file}")
        return ""  # Let inference handle it

    def get_fallback_code(self, task: Task) -> str:
        logger.debug(f"Generating fallback JavaScript for task={task.task_id}")
        output_file = task.parameters.get("output_file", "app.js")
        return f"""let scene = new THREE.Scene();
let camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
let renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('gameCanvas') }});
renderer.setSize(window.innerWidth, window.innerHeight);
let object = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({{ color: 0x00ff00 }}));
scene.add(object);
camera.position.z = 5;
function animate() {{
    requestAnimationFrame(animate);
    object.rotation.x += 0.01;
    renderer.render(scene, camera);
}}
animate();
"""

class HTMLHandler(LanguageHandler):
    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating HTML prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} based on the task description. "
            "Include a canvas (id='gameCanvas'), UI div (id='ui') with timer (span#timer), speed (span#speed), standings (table#standings), and start/reset button (button#startReset). "
            "Load Three.js and three-noise from CDNs. Include <script src='drone_game.js'>. "
            "Return clean HTML code, no JavaScript, no comments, no markdown."
        )

    def get_test_prompt(self, code: str) -> str:
        logger.debug("Generating HTML test prompt")
        return (
            f"Given HTML code:\n{code}\n\n"
            "Generate Jest tests for the HTML structure. "
            "Test presence of canvas, UI elements, and script tags. "
            "Return raw Jest code, no comments, no markdown."
        )

    def validate_code(self, code: str) -> bool:
        required = ["<html", "<body", "<canvas", "<script"]
        valid = bool(code.strip() and all(kw in code.lower() for kw in required))
        logger.debug(f"HTML validation: {'valid' if valid else 'invalid'}, keywords={required}")
        return valid

    def get_code(self, task: Task, output_file: str) -> str:
        logger.debug(f"Generating HTML code for task={task.task_id}, output_file={output_file}")
        title = task.parameters.get("title", "Drone Racing Game")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ margin: 0; background: #000; overflow: hidden; }}
        #gameCanvas {{ display: block; width: 100%; height: 100%; }}
        #ui {{ position: absolute; top: 10px; left: 10px; color: white; font-family: Arial, sans-serif; font-size: 16px; }}
        #ui div {{ margin-bottom: 5px; }}
        #standings {{ background: rgba(0, 0, 0, 0.7); padding: 10px; border-radius: 5px; }}
        #standings table {{ border-collapse: collapse; }}
        #standings th, #standings td {{ padding: 5px; border: 1px solid #fff; }}
        #startReset {{ padding: 10px 20px; background: #007bff; border: none; color: white; cursor: pointer; border-radius: 5px; }}
        #startReset:hover {{ background: #0056b3; }}
    </style>
</head>
<body>
    <canvas id="gameCanvas"></canvas>
    <div id="ui">
        <div>Timer: <span id="timer">0</span>s</div>
        <div>Speed: <span id="speed">0</span></div>
        <div id="standings"><table></table></div>
        <button id="startReset">Start</button>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://unpkg.com/three-noise/build/three-noise.min.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>"""

    def get_fallback_code(self, task: Task) -> str:
        logger.debug(f"Generating fallback HTML for task={task.task_id}")
        return self.get_code(task, task.parameters.get("output_file", "drone_game.html"))

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

    def get_code(self, task: Task, output_file: str) -> str:
        logger.debug("Python code requested, not implemented")
        return ""

    def get_fallback_code(self, task: Task) -> str:
        logger.debug("Python fallback code requested, not implemented")
        return ""

LANGUAGE_HANDLERS: Dict[str, LanguageHandler] = {
    "javascript": JavaScriptHandler(),
    "html": HTMLHandler(),
    "python": PythonHandler()
}
