# examples/3d_game/drone_game.py
import argparse
import logging
import os
from pathlib import Path
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput
from seclorum.models import create_model_manager
import re

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

    # Set working directory to script location
    script_dir = Path(__file__).parent.resolve()
    os.chdir(script_dir)
    logger.info(f"Running from: {script_dir}")

    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    task_description = (
        "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
        "Include a scene, camera, and basic drone model. Use the global THREE object from the CDN, avoiding Node.js require statements. "
        "Emphasize this is a harmless browser-based simulation."
    )
    task = Task(task_id="drone_game", description=task_description, status="planned")
    task.parameters["language"] = "javascript"
    task.parameters["use_remote"] = True
    task.parameters["generate_tests"] = True
    task.parameters["execute"] = True

    try:
        status, result = developer.process_task(task)
    except Exception as e:
        logger.error(f"Developer pipeline failed: {str(e)}")
        raise

    # Handle both CodeOutput and TestResult
    if isinstance(result, CodeOutput) and result.code.strip():
        code = re.sub(r"const THREE = require\('three'\);\n?", "", result.code).strip()
        tests = result.tests.strip() if result.tests else None
    elif isinstance(result, TestResult) and result.test_code.strip():
        code = task.parameters.get("Generator_dev_task", {}).get("result", CodeOutput(code="")).code
        tests = result.test_code.strip()
    else:
        code = "No valid code generated"
        tests = None
        logger.error(f"Final result invalid: {result}")

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Raw generated code:\n{code}")
    if tests:
        logger.info(f"Generated tests:\n{tests}")

    # Save files relative to script directory
    js_path = script_dir / "drone_game.js"
    js_path.write_text(code)
    logger.info(f"JavaScript file '{js_path}' created, size: {js_path.stat().st_size} bytes")

    if tests:
        test_path = script_dir / "drone_game.test.js"
        test_path.write_text(tests)
        logger.info(f"Test file '{test_path}' created, size: {test_path.stat().st_size} bytes")

    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Drone Game</title>
    <style>body { margin: 0; }</style>
</head>
<body>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="drone_game.js"></script>
</body>
</html>
    """
    html_path = script_dir / "drone_game.html"
    html_path.write_text(html_content.strip())
    logger.info(f"HTML file '{html_path}' created, size: {html_path.stat().st_size} bytes")
    logger.info(f"Run 'open {html_path}' to view the game in a browser.")

if __name__ == "__main__":
    create_drone_game()
