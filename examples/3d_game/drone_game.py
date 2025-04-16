# examples/3d_game/drone_game.py
import argparse
import logging
import os
import re
from pathlib import Path
from seclorum.agents.developer import Developer
from seclorum.models import CodeOutput
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
    parser.add_argument("--remote", action="store_true", default=True, help="Use remote inference (google_ai_studio).")
    parser.add_argument("--model", default="gemini-1.5-flash", help="Model name for inference (default: gemini-1.5-flash).")
    parser.add_argument("--timeout", type=int, default=30, help="Inference timeout in seconds (default: 30).")
    args = parser.parse_args()

    logger = setup_logging(args.summary)
    logger.debug(f"Running from: {os.getcwd()}")
    logger.debug(f"Arguments: remote={args.remote}, model={args.model}, timeout={args.timeout}")

    model_manager = create_model_manager(provider="google_ai_studio", model_name=args.model)
    developer = Developer("drone_game_session", model_manager)

    # Define tasks for JavaScript and HTML
    js_task = TaskFactory.create_code_task(
        description=(
            "Create JavaScript code for a Three.js game with a player-controlled drone (Arrow keys/W/S) in a 3D scene. "
            "Drones race across a scrolling landscape with mountains, valleys, and flatlands using Perlin noise (via three-noise CDN). "
            "Include scene, camera, ambient/directional lighting, and a sphere drone model. Use global THREE object from CDN (no import statements). "
            "Implement race mechanics: timer, checkpoints (score points), standings (time-based ranking), win condition (first to all checkpoints or fastest time). "
            "Add static obstacles (trees, rocks) and AI drones with A* pathfinding to checkpoints, avoiding obstacles. "
            "Reference HTML elements (canvas#gameCanvas, div#ui, span#timer, span#speed, table#standings, button#startReset) for UI integration."
        ),
        language="javascript",
        output_file="drone_game.js",
        generate_tests=True,
        execute=True,
        use_remote=args.remote,
        timeout=args.timeout
    )

    html_task = TaskFactory.create_code_task(
        description=(
            "Create HTML code for a Three.js drone racing game. "
            "Include a full-screen canvas (id='gameCanvas') for the game. "
            "Add a UI div (id='ui') with timer (span#timer), speed (span#speed), standings table (table#standings), and a blue start/reset button (button#startReset) with hover effects. "
            "Load Three.js and three-noise from CDNs (https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js, https://unpkg.com/three-noise/build/three-noise.min.js). "
            "Include <script src='drone_game.js'> to load the game logic. "
            "Use CSS for black background, white UI text, semi-transparent standings background, and blue button styling."
        ),
        language="html",
        output_file="drone_game.html",
        generate_tests=True,
        execute=True,
        use_remote=args.remote,
        timeout=args.timeout
    )

    output_dir = Path("examples/3d_game")
    output_dir.mkdir(exist_ok=True)

    # Process both tasks
    outputs = []
    for task in [js_task, html_task]:
        status, result = None, None
        try:
            status, result = developer.process_task(task)
            if status is None or result is None:
                raise ValueError(f"Developer returned None for {task.output_file}")
        except Exception as e:
            logger.error(f"Developer pipeline failed for {task.output_file}: {str(e)}")
            status = "failed"
            result = None

        if status in ["generated", "tested", "executed"] and result and isinstance(result, CodeOutput):
            outputs.append({
                "output_file": str(output_dir / task.output_file),
                "code": result.code,
                "tests": result.tests
            })

    # Fallback if pipeline fails
    if not outputs or len(outputs) < 2:
        logger.warning(f"Insufficient outputs generated (got {len(outputs)}), falling back to default code")
        outputs = [
            {
                "output_file": str(output_dir / "drone_game.js"),
                "code": """
// Assumes global THREE and Noise from CDNs
let scene, camera, renderer, playerDrone, aiDrones = [], terrain, checkpoints = [], obstacles = [], timer = 0, standings = [];
const clock = new THREE.Clock();

init();
animate();

function init() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gameCanvas') });
    renderer.setSize(window.innerWidth, window.innerHeight);

    // Terrain with Perlin noise
    const terrainGeometry = new THREE.PlaneGeometry(1000, 1000, 100, 100);
    const noise = new Noise({ type: 'perlin', scale: 0.05, octaves: 4, persistence: 0.5, lacunarity: 2 });
    const vertices = terrainGeometry.attributes.position.array;
    for (let i = 2; i < vertices.length; i += 3) {
        const x = vertices[i-2], y = vertices[i-1];
        vertices[i] = noise.get(x, y) * 30;
    }
    terrainGeometry.attributes.position.needsUpdate = true;
    terrainGeometry.computeVertexNormals();
    terrain = new THREE.Mesh(terrainGeometry, new THREE.MeshStandardMaterial({ color: 0x228B22, roughness: 0.8 }));
    terrain.rotation.x = -Math.PI / 2;
    scene.add(terrain);

    // Lighting
    scene.add(new THREE.AmbientLight(0x404040));
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight.position.set(0, 100, 50);
    scene.add(directionalLight);

    // Player Drone
    playerDrone = createDrone(0x0000ff, { x: 0, y: 10, z: 0 });
    playerDrone.momentum = new THREE.Vector3();
    scene.add(playerDrone);

    // AI Drones
    for (let i = 0; i < 3; i++) {
        const aiDrone = createDrone(0xff0000, { x: i * 20 - 20, y: 10, z: 0 });
        aiDrone.path = [];
        aiDrone.targetCheckpoint = 0;
        scene.add(aiDrone);
        aiDrones.push(aiDrone);
    }

    // Checkpoints
    for (let i = 0; i < 6; i++) {
        const checkpoint = new THREE.Mesh(
            new THREE.TorusGeometry(8, 1, 16, 100),
            new THREE.MeshBasicMaterial({ color: 0xffff00 })
        );
        checkpoint.position.set(Math.random() * 100 - 50, 10, -i * 150 - 50);
        scene.add(checkpoint);
        checkpoints.push(checkpoint);
    }

    // Obstacles
    for (let i = 0; i < 20; i++) {
        const type = Math.random() < 0.5 ? 'tree' : 'rock';
        const obstacle = new THREE.Mesh(
            type === 'tree' ? new THREE.CylinderGeometry(2, 2, 15, 16) : new THREE.BoxGeometry(5, 5, 5),
            new THREE.MeshStandardMaterial({ color: type === 'tree' ? 0x8B4513 : 0x808080 })
        );
        obstacle.position.set(Math.random() * 200 - 100, type === 'tree' ? 7.5 : 2.5, Math.random() * -800 - 50);
        scene.add(obstacle);
        obstacles.push(obstacle);
    }

    // Camera
    camera.position.set(0, 30, 50);
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    document.getElementById('startReset').addEventListener('click', startRace);

    updateStandings();
}

function createDrone(color, pos) {
    const drone = new THREE.Mesh(
        new THREE.SphereGeometry(2, 16, 16),
        new THREE.MeshStandardMaterial({ color })
    );
    drone.position.set(pos.x, pos.y, pos.z);
    drone.checkpoints = [];
    drone.time = 0;
    return drone;
}

function onKeyDown(event) {
    playerDrone.controls = playerDrone.controls || {};
    switch (event.key) {
        case 'ArrowUp': case 'w': playerDrone.controls.forward = true; break;
        case 'ArrowDown': case 's': playerDrone.controls.backward = true; break;
        case 'ArrowLeft': playerDrone.controls.left = true; break;
        case 'ArrowRight': playerDrone.controls.right = true; break;
    }
}

function onKeyUp(event) {
    playerDrone.controls = playerDrone.controls || {};
    switch (event.key) {
        case 'ArrowUp': case 'w': playerDrone.controls.forward = false; break;
        case 'ArrowDown': case 's': playerDrone.controls.backward = false; break;
        case 'ArrowLeft': playerDrone.controls.left = false; break;
        case 'ArrowRight': playerDrone.controls.right = false; break;
    }
}

function startRace() {
    timer = 0;
    standings = [];
    playerDrone.position.set(0, 10, 0);
    playerDrone.momentum.set(0, 0, 0);
    playerDrone.checkpoints = [];
    playerDrone.time = 0;
    aiDrones.forEach((d, i) => {
        d.position.set(i * 20 - 20, 10, 0);
        d.checkpoints = [];
        d.time = 0;
        d.targetCheckpoint = 0;
        d.path = [];
    });
    updateStandings();
}

function updatePlayerDrone(delta) {
    const accel = 0.5, friction = 0.9, maxSpeed = 5;
    playerDrone.controls = playerDrone.controls || {};
    const move = new THREE.Vector3();
    if (playerDrone.controls.forward) move.z -= accel;
    if (playerDrone.controls.backward) move.z += accel;
    if (playerDrone.controls.left) move.x -= accel;
    if (playerDrone.controls.right) move.x += accel;
    playerDrone.momentum.add(move.multiplyScalar(delta));
    playerDrone.momentum.clampLength(0, maxSpeed);
    playerDrone.momentum.multiplyScalar(friction);
    playerDrone.position.add(playerDrone.momentum);
    playerDrone.position.y = Math.max(10, terrain.getHeightAt ? terrain.getHeightAt(playerDrone.position.x, playerDrone.position.z) + 10 : 10);
}

function updateAIDrones(delta) {
    aiDrones.forEach(d => {
        if (d.targetCheckpoint >= checkpoints.length) return;
        const target = checkpoints[d.targetCheckpoint].position;
        if (d.path.length === 0 || d.position.distanceTo(d.path[d.path.length - 1]) < 5) {
            d.path = aStarPath(d.position, target, obstacles);
        }
        if (d.path.length > 0) {
            const next = d.path.shift();
            const direction = next.clone().sub(d.position).normalize();
            d.position.add(direction.multiplyScalar(3 * delta));
            d.position.y = Math.max(10, terrain.getHeightAt ? terrain.getHeightAt(d.position.x, d.position.z) + 10 : 10);
        }
    });
}

function aStarPath(start, goal, obstacles) {
    const gridSize = 10, grid = [];
    for (let x = -500; x <= 500; x += gridSize) {
        grid[x] = [];
        for (let z = -1000; z <= 0; z += gridSize) {
            grid[x][z] = obstacles.some(o => new THREE.Vector3(x, 10, z).distanceTo(o.position) < 10) ? Infinity : 1;
        }
    }
    const open = [{ pos: start.clone(), g: 0, h: start.distanceTo(goal), f: start.distanceTo(goal), path: [] }];
    const closed = new Set();
    while (open.length) {
        open.sort((a, b) => a.f - b.f);
        const current = open.shift();
        const key = `${Math.round(current.pos.x / gridSize)},${Math.round(current.pos.z / gridSize)}`;
        if (closed.has(key)) continue;
        closed.add(key);
        if (current.pos.distanceTo(goal) < 10) {
            return current.path.concat([goal]);
        }
        for (let dx of [-gridSize, 0, gridSize]) {
            for (let dz of [-gridSize, 0, gridSize]) {
                if (dx === 0 && dz === 0) continue;
                const nextPos = current.pos.clone().add(new THREE.Vector3(dx, 0, dz));
                const nextKey = `${Math.round(nextPos.x / gridSize)},${Math.round(nextPos.z / gridSize)}`;
                if (closed.has(nextKey) || (grid[Math.round(nextPos.x)] && grid[Math.round(nextPos.x)][Math.round(nextPos.z)] === Infinity)) continue;
                const g = current.g + gridSize;
                const h = nextPos.distanceTo(goal);
                open.push({ pos: nextPos, g, h, f: g + h, path: current.path.concat([nextPos]) });
            }
        }
    }
    return [];
}

function checkCollisions() {
    const drones = [playerDrone, ...aiDrones];
    drones.forEach((d, i) => {
        checkpoints.forEach((c, j) => {
            if (!d.checkpoints.includes(j) && d.position.distanceTo(c.position) < 8) {
                d.checkpoints.push(j);
                if (d.checkpoints.length === checkpoints.length) {
                    d.time = timer;
                    updateStandings();
                }
            }
        });
        obstacles.forEach(o => {
            if (d.position.distanceTo(o.position) < 5) {
                d.momentum ? d.momentum.multiplyScalar(0.5) : d.position.set(d.position.x, 10, d.position.z);
                if (d === playerDrone) standings.push({ drone: i + 1, time: Infinity, penalty: true });
            }
        });
    });
}

function updateStandings() {
    const drones = [playerDrone, ...aiDrones];
    standings = drones.map((d, i) => ({
        drone: i + 1,
        checkpoints: d.checkpoints.length,
        time: d.time || (d.checkpoints.length === checkpoints.length ? timer : Infinity)
    }));
    standings.sort((a, b) => b.checkpoints - a.checkpoints || a.time - b.time);
    const table = document.getElementById('standings');
    table.innerHTML = '<tr><th>Drone</th><th>Checkpoints</th><th>Time</th></tr>' +
        standings.map(s => `<tr><td>${s.drone}</td><td>${s.checkpoints}/${checkpoints.length}</td><td>${s.time === Infinity ? '-' : s.time.toFixed(1)}</td></tr>`).join('');
    if (standings.some(s => s.checkpoints === checkpoints.length)) {
        const winner = standings[0];
        table.innerHTML += `<tr><td colspan="3">Drone ${winner.drone} Wins!</td></tr>`;
    }
}

function updateUI() {
    document.getElementById('timer').innerText = timer.toFixed(1);
    document.getElementById('speed').innerText = playerDrone.momentum ? playerDrone.momentum.length().toFixed(1) : '0';
}

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    timer += delta;

    updatePlayerDrone(delta);
    updateAIDrones(delta);
    checkCollisions();
    updateUI();

    camera.position.lerp(
        playerDrone.position.clone().add(new THREE.Vector3(0, 20, 30)),
        0.1
    );
    camera.lookAt(playerDrone.position);
    renderer.render(scene, camera);
}
""",
                "tests": """
describe('Drone Racing Game', () => {
    beforeEach(() => {
        window.innerWidth = 500;
        window.innerHeight = 500;
        document.body.innerHTML = `
            <canvas id="gameCanvas"></canvas>
            <div id="ui">
                <div>Timer: <span id="timer">0</span>s</div>
                <div>Speed: <span id="speed">0</span></div>
                <table id="standings"></table>
                <button id="startReset">Start</button>
            </div>`;
        jest.spyOn(window, 'requestAnimationFrame').mockImplementation(cb => cb());
        init();
    });

    test('initializes scene and drones', () => {
        expect(scene).toBeDefined();
        expect(camera).toBeDefined();
        expect(renderer).toBeDefined();
        expect(playerDrone).toBeDefined();
        expect(aiDrones.length).toBe(3);
        expect(terrain).toBeDefined();
        expect(checkpoints.length).toBe(6);
        expect(obstacles.length).toBe(20);
    });

    test('handles player controls with momentum', () => {
        const initialPos = playerDrone.position.clone();
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }));
        animate();
        expect(playerDrone.position.z).toBeLessThan(initialPos.z);
        window.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowUp' }));
        animate();
        expect(playerDrone.momentum.length()).toBeLessThan(1);
    });

    test('moves AI drones with pathfinding', () => {
        const aiDrone = aiDrones[0];
        const initialPos = aiDrone.position.clone();
        animate();
        expect(aiDrone.position.distanceTo(initialPos)).toBeGreaterThan(0);
        expect(aiDrone.path.length).toBeGreaterThan(0);
    });

    test('updates standings table', () => {
        playerDrone.checkpoints = [0, 1];
        updateStandings();
        const table = document.getElementById('standings');
        expect(table.innerHTML).toContain('Drone 1');
        expect(table.innerHTML).toContain('2/6');
    });

    test('detects checkpoint collisions', () => {
        playerDrone.position.copy(checkpoints[0].position);
        checkCollisions();
        expect(playerDrone.checkpoints).toContain(0);
        playerDrone.checkpoints = Array.from({ length: checkpoints.length }, (_, i) => i);
        checkCollisions();
        expect(standings.some(s => s.drone === 1 && s.time > 0)).toBe(true);
    });

    test('penalizes obstacle collisions', () => {
        playerDrone.position.copy(obstacles[0].position);
        checkCollisions();
        expect(standings.some(s => s.drone === 1 && s.penalty)).toBe(true);
    });

    test('resets race on button click', () => {
        playerDrone.checkpoints = [0];
        document.getElementById('startReset').click();
        expect(playerDrone.checkpoints.length).toBe(0);
        expect(timer).toBe(0);
    });

    afterEach(() => {
        window.requestAnimationFrame.mockRestore();
        document.body.innerHTML = '';
    });
});
"""
            },
            {
                "output_file": str(output_dir / "drone_game.html"),
                "code": """
<!DOCTYPE html>
<html>
<head>
    <title>Drone Racing Game</title>
    <style>
        body { margin: 0; background: #000; overflow: hidden; }
        #gameCanvas { display: block; width: 100%; height: 100%; }
        #ui { position: absolute; top: 10px; left: 10px; color: white; font-family: Arial, sans-serif; font-size: 16px; }
        #ui div { margin-bottom: 5px; }
        #standings { background: rgba(0, 0, 0, 0.7); padding: 10px; border-radius: 5px; }
        #standings table { border-collapse: collapse; }
        #standings th, #standings td { padding: 5px; border: 1px solid #fff; }
        #startReset { padding: 10px 20px; background: #007bff; border: none; color: white; cursor: pointer; border-radius: 5px; }
        #startReset:hover { background: #0056b3; }
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
</html>
""",
                "tests": """
describe('Drone Game UI', () => {
    beforeEach(() => {
        document.body.innerHTML = `
            <canvas id="gameCanvas"></canvas>
            <div id="ui">
                <div>Timer: <span id="timer">0</span>s</div>
                <div>Speed: <span id="speed">0</span></div>
                <div id="standings"><table></table></div>
                <button id="startReset">Start</button>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
            <script src="https://unpkg.com/three-noise/build/three-noise.min.js"></script>
            <script src="drone_game.js"></script>`;
    });

    test('has canvas and UI elements', () => {
        expect(document.getElementById('gameCanvas')).toBeDefined();
        expect(document.getElementById('timer')).toBeDefined();
        expect(document.getElementById('speed')).toBeDefined();
        expect(document.getElementById('standings')).toBeDefined();
        expect(document.getElementById('startReset')).toBeDefined();
    });

    test('includes required scripts', () => {
        const scripts = Array.from(document.getElementsByTagName('script')).map(s => s.src);
        expect(scripts.some(src => src.includes('three.min.js'))).toBe(true);
        expect(scripts.some(src => src.includes('three-noise'))).toBe(true);
        expect(scripts.includes('drone_game.js')).toBe(true);
    });

    test('styles start button correctly', () => {
        const button = document.getElementById('startReset');
        expect(window.getComputedStyle(button).backgroundColor).toMatch(/rgba?\(0, 123, 255/);
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });
});
"""
            }
        ]

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
                test_file = output_file.replace(".js", ".test.js").replace(".html", ".html.test.js")
                with open(test_file, "w") as f:
                    f.write(tests)
                logger.info(f"Test file '{test_file}' created, size: {os.path.getsize(test_file)} bytes")

    logger.info(f"Task completed with status: {status or 'fallback'}")
    logger.info(f"Run 'open examples/3d_game/drone_game.html' to view the game in a browser.")
    logger.info(f"To test: 'cd examples/3d_game && npx jest *.test.js'")

if __name__ == "__main__":
    create_drone_game()
