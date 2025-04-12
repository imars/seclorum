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
    parser = argparse.ArgumentParser(description="Generate a Three.js drone racing game.")
    parser.add_argument("--summary", action="store_true", help="Output a summary of key events only.")
    args = parser.parse_args()

    logger = setup_logging(args.summary)
    logger.info(f"Running from: {os.getcwd()}")

    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    task = TaskFactory.create_code_task(
        description=(
            "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
            "Drones can race against each other across a 3D scrolling landscape of mountains, valleys, flatlands, and obstacles. "
            "Include a scene, camera, lighting, and a nice drone model. Use the global THREE object from a CDN, avoiding Node.js require statements. "
            "Implement race mechanics with a timer, checkpoints, and win conditions. Include HTML UI for timer, speed, standings, and start/reset buttons. "
            "Emphasize this is a harmless browser-based racing simulation."
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

    outputs = []
    for key, value in task.parameters.items():
        if not isinstance(value, dict):
            logger.debug(f"Skipping invalid parameter value for {key}: {value}")
            continue
        if "output_file" in value and isinstance(value.get("result"), CodeOutput) and value["result"].code.strip():
            outputs.append({
                "output_file": value["output_file"],
                "code": value["result"].code,
                "tests": value["result"].tests
            })

    if not outputs:
        logger.error("No valid outputs generated, falling back to default code")
        outputs = [{
            "output_file": "drone_game.js",
            "code": """
let scene, camera, renderer, drones, terrain, timer = 0, checkpoints = [];
const clock = new THREE.Clock();

init();
animate();

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
  renderer.setSize(window.innerWidth, window.innerHeight);

  const ambientLight = new THREE.AmbientLight(0x404040);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  scene.add(directionalLight);

  const geometry = new THREE.PlaneGeometry(1000, 1000, 50, 50);
  const vertices = geometry.attributes.position.array;
  for (let i = 2; i < vertices.length; i += 3) {
    vertices[i] = Math.sin(i * 0.1) * 10 + Math.random() * 5;
  }
  geometry.attributes.position.needsUpdate = true;
  terrain = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color: 0x00ff00}));
  terrain.rotation.x = -Math.PI / 2;
  scene.add(terrain);

  createDrones(3);
  createCheckpoints();
  createObstacles();

  camera.position.set(0, 50, 100);
  window.addEventListener('keydown', onKeyDown);
  document.getElementById('startButton').addEventListener('click', startRace);
}

function createDrones(numDrones) {
  drones = [];
  for (let i = 0; i < numDrones; i++) {
    const drone = new THREE.Mesh(new THREE.BoxGeometry(1,1,1), new THREE.MeshBasicMaterial({color: i === 0 ? 0x0000ff : 0x00ff00}));
    drone.position.set(i * 20, 10, 0);
    scene.add(drone);
    drones.push({ model: drone, speed: 0, acceleration: 0.1, checkpoints: [] });
  }
}

function createCheckpoints() {
  for (let i = 0; i < 5; i++) {
    const checkpoint = new THREE.Mesh(new THREE.TorusGeometry(5, 0.5, 16, 100), new THREE.MeshBasicMaterial({color: 0xffff00}));
    checkpoint.position.set(Math.random() * 200 - 100, 10, -i * 100);
    scene.add(checkpoint);
    checkpoints.push(checkpoint);
  }
}

function createObstacles() {
  for (let i = 0; i < 10; i++) {
    const obstacle = new THREE.Mesh(new THREE.BoxGeometry(5, 10, 5), new THREE.MeshBasicMaterial({color: 0xff0000}));
    obstacle.position.set(Math.random() * 200 - 100, 5, Math.random() * -500);
    scene.add(obstacle);
  }
}

function onKeyDown(event) {
  const speedIncrement = 0.5;
  switch (event.key) {
    case 'ArrowUp': drones[0].speed += speedIncrement; break;
    case 'ArrowDown': drones[0].speed -= speedIncrement; break;
    case 'ArrowLeft': drones[0].model.position.x -= 1; break;
    case 'ArrowRight': drones[0].model.position.x += 1; break;
    case 'KeyW': drones[0].model.position.y += 1; break;
    case 'KeyS': drones[0].model.position.y -= 1; break;
  }
}

function startRace() {
  timer = 0;
  drones.forEach(d => { d.checkpoints = []; d.model.position.set(0, 10, 0); });
  document.getElementById('standings').innerText = '-';
}

function updateUI() {
  document.getElementById('timer').innerText = timer.toFixed(1);
  document.getElementById('speed').innerText = drones[0].speed.toFixed(1);
}

function checkCollisions() {
  drones.forEach((d, idx) => {
    checkpoints.forEach((c, i) => {
      if (d.model.position.distanceTo(c.position) < 5 && !d.checkpoints.includes(i)) {
        d.checkpoints.push(i);
        if (d.checkpoints.length === checkpoints.length) {
          document.getElementById('standings').innerText = `Drone ${idx + 1} Wins!`;
        }
      }
    });
  });
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  timer += delta;
  drones.forEach(d => {
    d.model.position.z -= d.speed;
    d.model.position.y = Math.max(10, d.model.position.y);
  });
  camera.position.z = drones[0].model.position.z + 50;
  camera.position.x = drones[0].model.position.x;
  camera.position.y = drones[0].model.position.y + 20;
  updateUI();
  checkCollisions();
  renderer.render(scene, camera);
}
""",
            "tests": """
describe('Drone Racing Game', () => {
  beforeEach(() => {
    window.innerWidth = 500;
    window.innerHeight = 500;
    document.body.innerHTML = '<canvas id="myCanvas"></canvas><div id="uiPanel"><span id="timer"></span><span id="speed"></span><span id="standings"></span><button id="startButton"></button></div>';
    init();
  });

  it('initializes scene and drones', () => {
    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(drones).toBeDefined();
    expect(drones.length).toBe(3);
  });

  it('generates procedural terrain', () => {
    expect(terrain).toBeDefined();
    expect(terrain.geometry.type).toBe('PlaneGeometry');
  });

  it('handles key controls', () => {
    const initialPos = drones[0].model.position.clone();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    expect(drones[0].model.position.x).toBe(initialPos.x + 1);
  });

  it('updates UI', () => {
    updateUI();
    expect(document.getElementById('timer').innerText).not.toBe('');
    expect(document.getElementById('speed').innerText).not.toBe('');
  });

  it('has checkpoints', () => {
    expect(checkpoints.length).toBe(5);
  });

  it('start button resets race', () => {
    document.getElementById('startButton').click();
    expect(document.getElementById('standings').innerText).toBe('-');
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });
});
"""
        }, {
            "output_file": "drone_game.html",
            "code": """
<!DOCTYPE html>
<html>
<head>
    <title>Drone Racing Game</title>
    <style>
        body { margin: 0; background: #222; color: white; }
        #myCanvas { display: block; }
        #uiPanel { background-color: rgba(0, 0, 0, 0.5); position: absolute; top: 10px; left: 10px; padding: 10px; font-family: Arial, sans-serif; }
        #uiPanel div { margin-bottom: 5px; }
        #startButton { background-color: #4CAF50; border: none; color: white; padding: 10px 20px; cursor: pointer; }
        #startButton:hover { background-color: #3e8e41; }
    </style>
</head>
<body>
    <canvas id="myCanvas"></canvas>
    <div id="uiPanel">
        <div>Timer: <span id="timer">0</span>s</div>
        <div>Speed: <span id="speed">0</span></div>
        <div>Standings: <span id="standings">-</span></div>
        <button id="startButton">Start</button>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>
""",
            "tests": """
describe('Drone Game UI', () => {
  beforeEach(() => {
    document.body.innerHTML = document.querySelector('html').innerHTML;
  });

  it('has UI elements', () => {
    expect(document.getElementById('myCanvas')).toBeDefined();
    expect(document.getElementById('timer')).toBeDefined();
    expect(document.getElementById('speed')).toBeDefined();
    expect(document.getElementById('standings')).toBeDefined();
    expect(document.getElementById('startButton')).toBeDefined();
  });

  it('includes Three.js script', () => {
    const scripts = document.getElementsByTagName('script');
    const threeJsScript = Array.from(scripts).find(s => s.src.includes('three.js'));
    expect(threeJsScript).toBeDefined();
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });
});
"""
        }]

    for output in outputs:
        output_file = output["output_file"]
        code = re.sub(r'const THREE = require\(\'three\'\);\n?|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?', '', output["code"]).strip()
        tests = output["tests"].strip() if output["tests"] else None

        if code and not code.lower().startswith("error"):
            with open(output_file, "w") as f:
                f.write(code)
            logger.info(f"File '{output_file}' created, size: {os.path.getsize(output_file)} bytes")

            if tests:
                test_file = output_file.replace(".js", ".test.js").replace(".html", ".html.test.js")
                with open(test_file, "w") as f:
                    f.write(tests)
                logger.info(f"Test file '{test_file}' created, size: {os.path.getsize(test_file)} bytes")

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Run 'open drone_game.html' to view the game in a browser.")

if __name__ == "__main__":
    create_drone_game()
