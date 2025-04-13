# seclorum/agents/generator.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
from typing import Tuple
import re
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Generator initialized for Task {task_id}, session_id={session_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        logger.debug(f"Generating code for task={task.task_id}, description={task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")

        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            return "failed", CodeOutput(code="", tests=None)

        try:
            if language == "html":
                code = self.generate_html(task)
            else:
                code_prompt = handler.get_code_prompt(task, output_file)
                use_remote = task.parameters.get("use_remote", False)
                raw_code = self.infer(code_prompt, task, use_remote=use_remote, use_context=False, max_tokens=4000)
                logger.debug(f"Raw inferred code for {output_file}:\n{raw_code[:200]}...")
                code = re.sub(r'```(?:javascript|html|python|cpp|css)?\n|\n```|[^\x00-\x7F]+', '', raw_code).strip()

            if not handler.validate_code(code):
                logger.warning(f"Invalid {language} code generated for {output_file}, falling back to default")
                code = self.generate_fallback(language, output_file)
                if not handler.validate_code(code):
                    logger.error(f"Fallback {language} code still invalid for {output_file}")
                    code = ""

            logger.debug(f"Generated code for {output_file}:\n{code[:200]}...")

            tests = None
            if task.parameters.get("generate_tests", False) and code and language == "javascript":
                test_prompt = handler.get_test_prompt(code)
                use_remote = task.parameters.get("use_remote", False)
                raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False, max_tokens=2000)
                logger.debug(f"Raw inferred tests for {output_file}:\n{raw_tests[:200]}...")
                tests = re.sub(r'```(?:javascript|html|python|cpp)?\n|\n```|[^\x00-\x7F]+', '', raw_tests).strip()
                if not tests.startswith(("describe(", "test(")):
                    logger.warning(f"Invalid Jest tests for {output_file}, discarding")
                    tests = None
                logger.debug(f"Generated tests for {output_file}:\n{tests[:200]}..." if tests else "No valid tests generated")

            result = CodeOutput(code=code, tests=tests)
            self.save_output(task, result, status="generated")
            self.commit_changes(f"Generated {language} code for {output_file}")
            return "generated", result
        except Exception as e:
            logger.error(f"Generation failed for {output_file}: {str(e)}")
            return "failed", CodeOutput(code="", tests=None)

    def generate_html(self, task: Task) -> str:
        logger.debug(f"Generating HTML for task={task.task_id}, output_file={task.parameters.get('output_file', 'unknown')}")
        html_code = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Drone Racing Game</title>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; background: #000; }
        canvas#myCanvas { display: block; }
        #ui { position: absolute; top: 10px; left: 10px; color: #fff; font-family: Arial; background: rgba(0, 0, 0, 0.5); padding: 10px; }
        #startReset { margin: 5px; padding: 10px; background: #007bff; color: #fff; border: none; cursor: pointer; }
        #startReset:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div id="ui">
        <span id="timer">0</span>s
        <br>
        <span id="speed">0</span>
        <br>
        <pre id="standings">-</pre>
        <button id="startReset">Start</button>
    </div>
    <canvas id="myCanvas"></canvas>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>"""
        return html_code

    def generate_fallback(self, language: str, output_file: str) -> str:
        logger.debug(f"Generating fallback code for language={language}, output_file={output_file}")
        if language == "javascript":
            return """let scene = new THREE.Scene();
let camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
let renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('myCanvas') });
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

let drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
drone.position.set(0, 0, 10);
scene.add(drone);

camera.position.set(0, -20, 15);
camera.lookAt(drone.position);

document.addEventListener('keydown', function(event) {
    switch (event.key) {
        case 'ArrowUp': drone.position.z += 0.5; break;
        case 'ArrowDown': drone.position.z -= 0.5; break;
        case 'ArrowLeft': drone.position.x -= 0.5; break;
        case 'ArrowRight': drone.position.x += 0.5; break;
        case 'w': drone.position.y += 0.5; break;
        case 's': drone.position.y -= 0.5; break;
    }
});

function animate() {
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}
animate();
"""
        elif language == "html":
            return self.generate_html(Task(task_id=self.task_id, description="Fallback HTML", parameters={"language": "html", "output_file": output_file}))
        return ""

    def start(self):
        logger.debug(f"Starting generator {self.name}")

    def stop(self):
        logger.debug(f"Stopping generator {self.name}")
