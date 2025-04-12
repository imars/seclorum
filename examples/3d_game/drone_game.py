# examples/3d_game/drone_game.py
import argparse
import logging
import os
import re
from pathlib import Path
from seclorum.agents.developer import Developer
from seclorum.models import CodeOutput, TestResult
from seclorum.models import create_model_manager
from seclorum.models.task import TaskFactory

class SummaryFilter(logging.Filter):
    def filter(self, record):
        key_phrases = [
            "Raw generated code",
            "Execution output",
            "Unexpected execution error",
            "Final result",
            "Task completed",
        ]
        return any(phrase in record.msg for phrase in key_phrases)

def setup_logging(summary_mode=False):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()

    if summary_mode:
        handler.addFilter(SummaryFilter())
        formatter = logging.Formatter("%(levelname)s: %(message)s")
    else:
        formatter = logging.Formatter("%(levelname)s:%(name)s: %(message)s")

    handler.setFormatter(formatter)
    logger.handlers = [handler]
    return logger

def create_drone_game():
    parser = argparse.ArgumentParser(description="Generate a Three.js drone game.")
    parser.add_argument("--summary", action="store_true", help="Output a summary of key events only.")
    args = parser.parse_args()

    logger = setup_logging(args.summary)
    logger.info(f"Running from: {os.getcwd()}")

    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    task = TaskFactory.create_code_task(
        description=(
            "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
            "Include a scene, camera, and basic drone model. Use the global THREE object from a CDN, avoiding Node.js require statements. "
            "Emphasize this is a harmless browser-based simulation."
        ),
        language="javascript",
        generate_tests=True,
        execute=True,
        use_remote=True
    )

    try:
        status, result = developer.process_task(task)
    except Exception as e:
        logger.error(f"Developer pipeline failed: {str(e)}")
        raise

    # Extract code and tests
    code = None
    tests = None
    if isinstance(result, CodeOutput) and result.code.strip():
        code = re.sub(r"const THREE = require\('three'\);\n?|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?", "", result.code).strip()
        tests = result.tests.strip() if result.tests else None
    elif isinstance(result, TestResult):
        debugger_key = f"Debugger_dev_task"
        if debugger_key in task.parameters:
            debug_output = task.parameters[debugger_key].get("result")
            if isinstance(debug_output, CodeOutput) and debug_output.code.strip():
                code = re.sub(r"const THREE = require\('three'\);\n?|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?", "", debug_output.code).strip()
                tests = debug_output.tests.strip() if debug_output.tests else None
        if not code:
            generator_key = f"Generator_dev_task"
            if generator_key in task.parameters:
                gen_output = task.parameters[generator_key].get("result")
                if isinstance(gen_output, CodeOutput) and gen_output.code.strip():
                    code = re.sub(r"const THREE = require\('three'\);\n?|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?", "", gen_output.code).strip()
                    tests = gen_output.tests.strip() if gen_output.tests else None

    if not code or code.lower().startswith("error"):
        logger.error(f"Final result invalid, falling back to default code")
        code = """
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 5, 10);
scene.add(camera);
const renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
renderer.setSize(window.innerWidth, window.innerHeight);

const droneGeometry = new THREE.BoxGeometry(1, 1, 1);
const droneMaterial = new THREE.MeshBasicMaterial({color: 0x0000ff});
const drone = new THREE.Mesh(droneGeometry, droneMaterial);
scene.add(drone);

const numStars = 1000;
const starsGeometry = new THREE.BufferGeometry();
const starPositions = new Float32Array(numStars * 3);
for (let i = 0; i < numStars; i++) {
  starPositions[i * 3] = Math.random() * 1000 - 500;
  starPositions[i * 3 + 1] = Math.random() * 1000 - 500;
  starPositions[i * 3 + 2] = Math.random() * 1000 - 500;
}
starsGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
const starsMaterial = new THREE.PointsMaterial({color: 0xffffff, size: 2});
const stars = new THREE.Points(starsGeometry, starsMaterial);
scene.add(stars);

let speed = 0.1;
const keysPressed = {};
document.addEventListener('keydown', (e) => {keysPressed[e.code] = true;});
document.addEventListener('keyup', (e) => {keysPressed[e.code] = false;});

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

function animate() {
  requestAnimationFrame(animate);
  if (keysPressed['ArrowUp']) drone.position.z -= speed;
  if (keysPressed['ArrowDown']) drone.position.z += speed;
  if (keysPressed['ArrowLeft']) drone.position.x -= speed;
  if (keysPressed['ArrowRight']) drone.position.x += speed;
  renderer.render(scene, camera);
}
animate();
"""
        tests = None

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Raw generated code:\n{code}")
    if tests:
        logger.info(f"Generated tests:\n{tests}")

    # Save the JavaScript code
    js_path = "drone_game.js"
    with open(js_path, "w") as f:
        f.write(code)
    logger.info(f"JavaScript file '{js_path}' created, size: {os.path.getsize(js_path)} bytes")

    # Save tests if generated
    if tests:
        test_path = "drone_game.test.js"
        with open(test_path, "w") as f:
            f.write(tests)
        logger.info(f"Test file '{test_path}' created, size: {os.path.getsize(test_path)} bytes")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Drone Game</title>
    <style>body {{ margin: 0; }}</style>
</head>
<body>
    <canvas id="myCanvas"></canvas>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>
    """
    html_path = "drone_game.html"
    with open(html_path, "w") as f:
        f.write(html_content)
    logger.info(f"HTML file '{html_path}' created, size: {os.path.getsize(html_path)} bytes")
    logger.info(f"Run 'open {html_path}' to view the game in a browser.")

if __name__ == "__main__":
    create_drone_game()
