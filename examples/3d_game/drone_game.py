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

    # Define tasks
    js_task = TaskFactory.create_code_task(
        description=(
            "Create JavaScript code for a Three.js drone racing game with a player-controlled drone in a 3D scene. "
            "Split code into four files: "
            "1. scene.js: Initialize THREE.Scene, PerspectiveCamera (75 FOV, 0.1 near, 1000 far), WebGLRenderer (canvas#gameCanvas), ambient (0x404040) and directional lighting (0xffffff, 0.5 intensity, position 0,100,50). "
            "2. terrain.js: Generate a scrolling landscape (PlaneGeometry, 1000x1000, 100x100 segments) with mountains/valleys using simplexNoise.createNoise2D() from https://cdn.jsdelivr.net/npm/simplex-noise@4.0.1/dist/simplex-noise.min.js. Scale noise by 0.02, height by 50. Use MeshStandardMaterial (color 0x228B22, roughness 0.8). "
            "3. drones.js: Implement player drone (blue sphere, radius 2, Arrow keys/W/S for movement, mouse for yaw/pitch orientation), AI drones (red spheres, A* pathfinding to checkpoints, advance to next checkpoint after each hit), checkpoints (6 yellow toruses, random x -50 to 50, z -50 to -950), obstacles (10 trees as cylinders, 10 rocks as boxes). "
            "4. ui.js: Manage UI: timer (span#timer, seconds), speed (span#speed, drone momentum), standings (table#standings, rank by checkpoints/time), blue start/reset button (button#startReset). "
            "Use global THREE from https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js and simplexNoise (no imports). "
            "Implement race mechanics: score points at checkpoints, win when all checkpoints hit. Check for simplexNoise availability, log error if missing."
        ),
        language="javascript",
        output_file="scene.js",
        output_files=["scene.js", "terrain.js", "drones.js", "ui.js"],
        generate_tests=True,
        execute=True,
        use_remote=args.remote,
        timeout=args.timeout
    )

    html_task = TaskFactory.create_code_task(
        description=(
            "Create HTML code for a Three.js drone racing game. "
            "Include a full-screen canvas (id='gameCanvas'). "
            "Add a UI div (id='ui') with timer (span#timer), speed (span#speed), standings table (table#standings), blue start/reset button (button#startReset, hover #0056b3). "
            "Load scripts in order: Three.js (https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js), simplex-noise (https://cdn.jsdelivr.net/npm/simplex-noise@4.0.1/dist/simplex-noise.min.js), scene.js, terrain.js, drones.js, ui.js. "
            "Use CSS: black background (#000), white UI text (Arial, 16px), semi-transparent standings (rgba(0,0,0,0.7)), blue button (#007bff). "
            "Add inline script to define simplexNoise fallback (flat terrain) if CDN fails. No JavaScript logic in HTML."
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
    fallback_dir = output_dir / "fallback"
    fallback_dir.mkdir(exist_ok=True)

    # Process tasks
    outputs = []
    for task in [js_task, html_task]:
        output_files = task.parameters.get("output_files", [task.parameters["output_file"]])
        status, result = None, None
        try:
            status, result = developer.process_task(task)
            logger.debug(f"Task {task.parameters['output_file']}: status={status}, result_type={type(result).__name__}, "
                        f"code_length={len(result.code) if result and hasattr(result, 'code') else 0}")
            if status is None or result is None:
                raise ValueError(f"Developer returned None for {task.parameters['output_file']}")
        except Exception as e:
            logger.error(f"Developer pipeline failed for {task.parameters['output_file']}: {str(e)}")
            status = "failed"
            result = None

        # Validate pipeline output
        if status in ["generated", "tested", "executed"] and result and isinstance(result, CodeOutput) and result.code.strip():
            is_valid = False
            if task.language == "javascript":
                is_valid = "THREE." in result.code and all(
                    f in (result.additional_files or {}) for f in output_files if f != task.parameters["output_file"]
                )
            elif task.language == "html":
                is_valid = "<html" in result.code and "<canvas" in result.code and "simplex-noise" in result.code
            if is_valid:
                outputs.append({
                    "output_file": str(output_dir / task.parameters["output_file"]),
                    "code": result.code,
                    "tests": result.tests
                })
                for additional_file, code in (result.additional_files or {}).items():
                    if code.strip():
                        outputs.append({
                            "output_file": str(output_dir / additional_file),
                            "code": code,
                            "tests": None
                        })
                logger.info(f"Pipeline output for {task.parameters['output_file']}: {len(result.code)} bytes")
                if result.additional_files:
                    logger.info(f"Additional files: {list(result.additional_files.keys())}")
            else:
                logger.warning(f"Invalid pipeline output for {task.parameters['output_file']}: expected {task.language}")
        else:
            logger.warning(f"No valid pipeline output for {task.parameters['output_file']}: status={status}, "
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
                logger.error(f"Fallback file {fallback_path} not found")
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
