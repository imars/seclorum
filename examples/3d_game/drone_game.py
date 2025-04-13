# examples/3d_game/drone_game.py
import argparse
import logging
import os
import re
from pathlib import Path
from seclorum.agents.developer import Developer
from seclorum.models import CodeOutput, CodeResult
from seclorum.models import create_model_manager
from seclorum.models.task import TaskFactory

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    logger.setLevel(logging.DEBUG if not summary_mode else logging.INFO)
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
    logger.debug(f"Running from: {os.getcwd()}")

    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    task = TaskFactory.create_code_task(
        description=(
            "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
            "Drones race across a 3D scrolling landscape of mountains, valleys, flatlands, and obstacles. "
            "Include a scene, camera, lighting, and a drone model. Use the global THREE object from a CDN. "
            "Implement race mechanics with a timer, checkpoints, and win conditions. Include HTML UI for timer, speed, standings, and start/reset buttons."
        ),
        language="javascript",
        generate_tests=True,
        execute=True,
        use_remote=True
    )

    output_dir = Path("examples/3d_game")
    output_dir.mkdir(exist_ok=True)

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
                "output_file": str(output_dir / value["output_file"]),
                "code": value["result"].code,
                "tests": value["result"].tests
            })

    if not outputs:
        logger.warning("No valid outputs generated, falling back to default code")
        outputs = [{
            "output_file": str(output_dir / "drone_game.js"),
            "code": """
let scene, camera, renderer, drones, terrain, timer = 0, checkpoints = [], obstacles = [];
const clock = new THREE.Clock();

init();
animate();

function init() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({canvas: document.getElementById('myCanvas')});
  renderer.setSize(window.innerWidth, window.innerHeight);

  scene.add(new THREE.AmbientLight(0x404040));
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(0, 100, 50);
  scene.add(directionalLight);

  const geometry = new THREE.PlaneGeometry(1000, 1000, 50, 50);
  const vertices = geometry.attributes.position.array;
  for (let i = 2; i < vertices.length; i += 3) {
    const x = vertices[i-2], y = vertices[i-1];
    vertices[i] = (Math.sin(x * 0.05) * Math.cos(y * 0.05) * 20) + (Math.random() * 5);
  }
  geometry.attributes.position.needsUpdate = true;
  geometry.computeVertexNormals();
  terrain = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color: 0x228B22, roughness: 0.8}));
  terrain.rotation.x = -Math.PI / 2;
  scene.add(terrain);

  createDrones(3);
  createCheckpoints();
  createObstacles();

  camera.position.set(0, 50, 100);
  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  document.getElementById('startReset').addEventListener('click', startRace);
}

function createDrones(numDrones) {
  drones = [];
  for (let i = 0; i < numDrones; i++) {
    const drone = new THREE.Mesh(
      new THREE.BoxGeometry(2, 1, 3),
      new THREE.MeshStandardMaterial({color: i === 0 ? 0x0000ff : 0xff0000})
    );
    drone.position.set(i * 20 - 20, 10, 0);
    scene.add(drone);
    drones.push({
      model: drone,
      speed: 0,
      strafe: 0,
      altitude: 10,
      maxSpeed: 5,
      acceleration: 0.2,
      checkpoints: [],
      isAI: i > 0
    });
  }
}

function createCheckpoints() {
  for (let i = 0; i < 6; i++) {
    const checkpoint = new THREE.Mesh(
      new THREE.TorusGeometry(8, 1, 16, 100),
      new THREE.MeshBasicMaterial({color: 0xffff00})
    );
    checkpoint.position.set(Math.random() * 100 - 50, 10, -i * 150 - 50);
    scene.add(checkpoint);
    checkpoints.push(checkpoint);
  }
}

function createObstacles() {
  for (let i = 0; i < 15; i++) {
    const obstacle = new THREE.Mesh(
      new THREE.BoxGeometry(5, 10, 5),
      new THREE.MeshStandardMaterial({color: 0x8B4513})
    );
    obstacle.position.set(Math.random() * 200 - 100, 5, Math.random() * -800 - 50);
    scene.add(obstacle);
    obstacles.push(obstacle);
  }
}

function onKeyDown(event) {
  const drone = drones[0];
  switch (event.key) {
    case 'ArrowUp': drone.acceleration = 0.2; break;
    case 'ArrowDown': drone.acceleration = -0.2; break;
    case 'ArrowLeft': drone.strafe = -1; break;
    case 'ArrowRight': drone.strafe = 1; break;
    case 'w': drone.altitude = Math.min(drone.altitude + 1, 50); break;
    case 's': drone.altitude = Math.max(drone.altitude - 1, 5); break;
  }
}

function onKeyUp(event) {
  const drone = drones[0];
  switch (event.key) {
    case 'ArrowUp':
    case 'ArrowDown': drone.acceleration = 0; break;
    case 'ArrowLeft':
    case 'ArrowRight': drone.strafe = 0; break;
  }
}

function startRace() {
  timer = 0;
  drones.forEach((d, i) => {
    d.checkpoints = [];
    d.model.position.set(i * 20 - 20, 10, 0);
    d.speed = 0;
    d.strafe = 0;
    d.altitude = 10;
  });
  document.getElementById('standings').innerText = '-';
}

function updateAI(drone, delta) {
  if (!drone.isAI) return;
  const target = checkpoints[drone.checkpoints.length] || checkpoints[0];
  const direction = new THREE.Vector3().subVectors(target.position, drone.model.position).normalize();
  drone.speed = Math.min(drone.speed + delta * 0.1, 3);
  drone.model.position.add(direction.multiplyScalar(drone.speed * delta));
  drone.altitude = Math.max(10, Math.min(20, target.position.y + 5));
}

function updateUI() {
  document.getElementById('timer').innerText = timer.toFixed(1);
  document.getElementById('speed').innerText = drones[0].speed.toFixed(1);
  let standings = '';
  drones.forEach((d, i) => {
    standings += `Drone ${i + 1}: ${d.checkpoints.length}/${checkpoints.length}\n`;
  });
  document.getElementById('standings').innerText = standings;
}

function checkCollisions() {
  drones.forEach((d, i) => {
    checkpoints.forEach((c, j) => {
      if (!d.checkpoints.includes(j) && d.model.position.distanceTo(c.position) < 8) {
        d.checkpoints.push(j);
        if (d.checkpoints.length === checkpoints.length) {
          document.getElementById('standings').innerText = `Drone ${i + 1} Wins!`;
        }
      }
    });
    obstacles.forEach(o => {
      if (d.model.position.distanceTo(o.position) < 5) {
        d.speed *= 0.5;
      }
    });
  });
}

function animate() {
  requestAnimationFrame(animate);
  const delta = clock.getDelta();
  timer += delta;

  drones.forEach((d, i) => {
    if (d.isAI) {
      updateAI(d, delta);
    } else {
      d.speed = Math.max(0, Math.min(d.speed + d.acceleration, d.maxSpeed));
      d.model.position.x += d.strafe * delta * 10;
      d.model.position.z -= d.speed * delta * 10;
      d.model.position.y = d.altitude;
    }
    d.model.position.y = Math.max(d.model.position.y, 5);
  });

  camera.position.set(drones[0].model.position.x, drones[0].model.position.y + 20, drones[0].model.position.z + 30);
  camera.lookAt(drones[0].model.position);
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
    document.body.innerHTML = '<canvas id="myCanvas"></canvas><div id="ui"><span id="timer"></span><span id="speed"></span><pre id="standings"></pre><button id="startReset"></button></div>';
    init();
  });

  test('initializes scene and drones', () => {
    expect(scene).toBeDefined();
    expect(camera).toBeDefined();
    expect(renderer).toBeDefined();
    expect(drones).toBeDefined();
    expect(drones.length).toBe(3);
    expect(terrain).toBeDefined();
  });

  test('handles player controls', () => {
    const initialPos = drones[0].model.position.clone();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    animate();
    expect(drones[0].model.position.x).toBeGreaterThan(initialPos.x);
    window.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowRight' }));
  });

  test('moves AI drones', () => {
    const aiDrone = drones[1];
    const initialPos = aiDrone.model.position.clone();
    animate();
    expect(aiDrone.model.position.distanceTo(initialPos)).toBeGreaterThan(0);
  });

  test('updates UI', () => {
    updateUI();
    expect(document.getElementById('timer').innerText).not.toBe('');
    expect(document.getElementById('speed').innerText).not.toBe('');
    expect(document.getElementById('standings').innerText).not.toBe('');
  });

  test('checks checkpoints and obstacles', () => {
    drones[0].model.position.set(checkpoints[0].position.x, 10, checkpoints[0].position.z);
    checkCollisions();
    expect(drones[0].checkpoints).toContain(0);
    drones[0].model.position.set(obstacles[0].position.x, 5, obstacles[0].position.z);
    const initialSpeed = drones[0].speed;
    checkCollisions();
    expect(drones[0].speed).toBeLessThanOrEqual(initialSpeed);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });
});
"""
        }, {
            "output_file": str(output_dir / "drone_game.html"),
            "code": """
<!DOCTYPE html>
<html>
<head>
    <title>Drone Racing Game</title>
    <style>
        body { margin: 0; background: #000; overflow: hidden; }
        #myCanvas { display: block; width: 100%; height: 100%; }
        #ui { position: absolute; top: 10px; left: 10px; color: white; font-family: Arial, sans-serif; font-size: 16px; }
        #ui div { margin-bottom: 5px; }
        #standings { white-space: pre; }
        #startReset { padding: 5px 10px; background: #007bff; border: none; color: white; cursor: pointer; }
        #startReset:hover { background: #0056b3; }
    </style>
</head>
<body>
    <canvas id="myCanvas"></canvas>
    <div id="ui">
        <div>Timer: <span id="timer">0</span>s</div>
        <div>Speed: <span id="speed">0</span></div>
        <div>Standings: <pre id="standings">-</pre></div>
        <button id="startReset">Start</button>
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>
""",
            "tests": """
describe('Drone Game UI', () => {
  beforeEach(() => {
    document.body.innerHTML = `<canvas id="myCanvas"></canvas>
      <div id="ui">
        <div>Timer: <span id="timer">0</span>s</div>
        <div>Speed: <span id="speed">0</span></div>
        <div>Standings: <pre id="standings">-</pre></div>
        <button id="startReset">Start</button>
      </div>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
      <script src="drone_game.js"></script>`;
  });

  test('has canvas and UI elements', () => {
    expect(document.getElementById('myCanvas')).toBeDefined();
    expect(document.getElementById('timer')).toBeDefined();
    expect(document.getElementById('speed')).toBeDefined();
    expect(document.getElementById('standings')).toBeDefined();
    expect(document.getElementById('startReset')).toBeDefined();
  });

  test('includes required scripts', () => {
    const scripts = Array.from(document.getElementsByTagName('script')).map(s => s.src);
    expect(scripts.some(src => src.includes('three.min.js'))).toBe(true);
    expect(scripts.includes('drone_game.js')).toBe(true);
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
            os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
            with open(output_file, "w") as f:
                f.write(code)
            logger.info(f"File '{output_file}' created, size: {os.path.getsize(output_file)} bytes")

            if tests:
                test_file = output_file.replace(".js", ".test.js").replace(".html", ".test.js")
                with open(test_file, "w") as f:
                    f.write(tests)
                logger.info(f"Test file '{test_file}' created, size: {os.path.getsize(test_file)} bytes")

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Run 'open examples/3d_game/drone_game.html' to view the game in a browser.")

if __name__ == "__main__":
    create_drone_game()
