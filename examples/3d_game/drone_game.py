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

    # Define tasks for JavaScript files and HTML
    tasks = [
        TaskFactory.create_code_task(
            description=(
                "Create JavaScript code for a Three.js drone racing game’s scene setup in scene.js. "
                "Initialize a THREE.Scene, PerspectiveCamera (75 FOV, 0.1 near, 1000 far), WebGLRenderer (using canvas#gameCanvas), and THREE.Clock. "
                "Set renderer size to window.innerWidth/innerHeight. "
                "Add ambient light (0x404040) and directional light (0xffffff, 0.5 intensity, position 0,100,50). "
                "Use global THREE from CDN https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js (no imports). "
                "Define initScene() to set up and expose scene, camera, renderer, clock globally."
            ),
            language="javascript",
            output_file="scene.js",
            generate_tests=True,
            execute=True,
            use_remote=args.remote,
            timeout=args.timeout
        ),
        TaskFactory.create_code_task(
            description=(
                "Create JavaScript code for a Three.js drone racing game’s terrain generation in terrain.js. "
                "Generate a 1000x1000 PlaneGeometry (100x100 segments) with simplexNoise.createNoise2D() from CDN https://cdn.jsdelivr.net/npm/simplex-noise@4.0.1/dist/simplex-noise.min.js. "
                "Apply noise(x * 0.02, y * 0.02) * 50 to vertex Z positions for prominent mountains/valleys. "
                "Use MeshStandardMaterial (color 0x228B22, roughness 0.8), rotate plane -90 degrees on X-axis. "
                "Use global THREE (no imports). Check simplexNoise availability, log error if missing. "
                "Define initTerrain() to create and add terrain to scene globally."
            ),
            language="javascript",
            output_file="terrain.js",
            generate_tests=True,
            execute=True,
            use_remote=args.remote,
            timeout=args.timeout
        ),
        TaskFactory.create_code_task(
            description=(
                "Create JavaScript code for a Three.js drone racing game’s drone logic in drones.js. "
                "Define createDrone(color, pos) for a sphere mesh (radius 2, 16 segments) with MeshStandardMaterial. "
                "Implement player drone (blue): Arrow keys/W/S for movement, mouse for yaw/pitch orientation (left/right for yaw ±45°, up/down for pitch ±45°). "
                "Implement 3 AI drones (red): use A* pathfinding to reach 6 checkpoints (yellow toruses, random x -50 to 50, z -50 to -950), advance to next checkpoint after each hit. "
                "Add 20 obstacles (10 trees as cylinders, 10 rocks as boxes). "
                "Use global THREE (no imports). Include race mechanics: score points at checkpoints, track completion time. "
                "Define initDrones(), updatePlayerDrone(delta), updateAIDrones(delta), checkCollisions(timer, standings, updateStandings) to manage drones and expose playerDrone, aiDrones, checkpoints, obstacles globally."
            ),
            language="javascript",
            output_file="drones.js",
            generate_tests=True,
            execute=True,
            use_remote=args.remote,
            timeout=args.timeout
        ),
        TaskFactory.create_code_task(
            description=(
                "Create JavaScript code for a Three.js drone racing game’s UI and animation in ui.js. "
                "Manage HTML elements: span#timer (race time in seconds), span#speed (drone speed), table#standings (rank drones by checkpoints/time), button#startReset (reset race). "
                "Implement animate() loop: update drones, collisions, UI, camera (follow player). "
                "Show 'Drone X Wins!' when a drone hits all checkpoints. "
                "Use global THREE (no imports). "
                "Define initUI(), startRace(), updateUI(), updateStandings(), animate() to manage UI and expose timer, standings globally."
            ),
            language="javascript",
            output_file="ui.js",
            generate_tests=True,
            execute=True,
            use_remote=args.remote,
            timeout=args.timeout
        ),
        TaskFactory.create_code_task(
            description=(
                "Create HTML code for a Three.js drone racing game in drone_game.html. "
                "Include a full-screen canvas (id='gameCanvas'). "
                "Add a UI div (id='ui') with timer (span#timer), speed (span#speed), standings table (table#standings), blue start/reset button (button#startReset, hover #0056b3). "
                "Load scripts in order with defer: Three.js (https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js), simplex-noise (https://cdn.jsdelivr.net/npm/simplex-noise@4.0.1/dist/simplex-noise.min.js), scene.js, terrain.js, drones.js, ui.js. "
                "Use CSS: black background (#000), white UI text (Arial, 16px), semi-transparent standings (rgba(0,0,0,0.7)), blue button (#007bff). "
                "Add inline script to define simplexNoise fallback (flat terrain) if CDN fails. Include final script to call initScene(), initTerrain(), initDrones(), initUI(), animate()."
            ),
            language="html",
            output_file="drone_game.html",
            generate_tests=True,
            execute=True,
            use_remote=args.remote,
            timeout=args.timeout
        )
    ]

    output_dir = Path("examples/3d_game")
    output_dir.mkdir(exist_ok=True)
    fallback_dir = output_dir / "fallback"
    fallback_dir.mkdir(exist_ok=True)

    # Process all tasks
    outputs = []
    for task in tasks:
        output_file = task.parameters["output_file"]
        status, result = None, None
        try:
            status, result = developer.process_task(task)
            logger.debug(f"Task {output_file}: status={status}, result_type={type(result).__name__}, "
                        f"code_length={len(result.code) if result and hasattr(result, 'code') else 0}")
            if status is None or result is None:
                raise ValueError(f"Developer returned None for {output_file}")
        except Exception as e:
            logger.error(f"Developer pipeline failed for {output_file}: {str(e)}")
            status = "failed"
            result = None

        # Validate pipeline output
        if status in ["generated", "tested", "executed"] and result and isinstance(result, CodeOutput) and result.code.strip():
            is_valid = False
            if task.language == "javascript":
                is_valid = "THREE." in result.code or "simplexNoise" in result.code
            elif task.language == "html":
                is_valid = "<html" in result.code and "<canvas" in result.code and "simplex-noise" in result.code
            if is_valid:
                outputs.append({
                    "output_file": str(output_dir / output_file),
                    "code": result.code,
                    "tests": result.tests
                })
                logger.info(f"Pipeline output for {output_file}: {len(result.code)} bytes")
            else:
                logger.warning(f"Invalid pipeline output for {output_file}: expected {task.language}")
        else:
            logger.warning(f"No valid pipeline output for {output_file}: status={status}, "
                          f"result_type={type(result).__name__ if result else 'None'}")

    # Fallback if insufficient outputs
    expected_files = {"scene.js", "terrain.js", "drones.js", "ui.js", "drone_game.html"}
    generated_files = {Path(o["output_file"]).name for o in outputs}
    if generated_files != expected_files:
        logger.warning(f"Insufficient outputs generated (got {generated_files}), falling back to default code")
        fallback_files = {
            "scene.js": fallback_dir / "scene.js",
            "terrain.js": fallback_dir / "terrain.js",
            "drones.js": fallback_dir / "drones.js",
            "ui.js": fallback_dir / "ui.js",
            "drone_game.html": fallback_dir / "drone_game.html"
        }
        for file_name, fallback_path in fallback_files.items():
            if not fallback_path.exists():
                logger.warning(f"Fallback file {fallback_path} not found, skipping")
                continue
            with open(fallback_path, "r") as f:
                code = f.read()
            outputs.append({
                "output_file": str(output_dir / file_name),
                "code": code,
                "tests": None
            })
            logger.info(f"Using fallback for {file_name}: {len(code)} bytes")

    # Write outputs
    for output in outputs:
        output_file = output["output_file"]
        code = re.sub(r'const THREE = require\(\'three\'\);\n?|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?', '', output["code"]).strip()
        tests = output["tests"].strip() if output.get("tests") else None

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
