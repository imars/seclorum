# examples/3d_game/drone_game.py
import argparse
import logging
import os
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput
from seclorum.models import create_model_manager

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
    logger.handlers = [handler]  # Clear and set single handler
    return logger

def create_drone_game():
    parser = argparse.ArgumentParser(description="Generate a Three.js drone game.")
    parser.add_argument("--summary", action="store_true", help="Output a summary of key events only.")
    args = parser.parse_args()

    logger = setup_logging(args.summary)

    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    task_description = (
        "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
        "Include a scene, camera, and basic drone model. Emphasize this is a harmless browser-based simulation."
    )
    task = Task(task_id="drone_game", description=task_description, status="planned")
    task.parameters["language"] = "javascript"
    task.parameters["use_remote"] = True
    task.parameters["generate_tests"] = True

    status, result = developer.process_task(task)

    # Ensure result is a CodeOutput with valid code
    if isinstance(result, CodeOutput) and result.code.strip():
        code = result.code
    else:
        code = "No valid code generated"
        logger.error(f"Final result invalid: {result}")

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Raw generated code:\n{code}")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Drone Game</title>
    <style>body {{ margin: 0; }}</style>
</head>
<body>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://unpkg.com/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script>
    {code}
    </script>
</body>
</html>
    """
    with open("drone_game.html", "w") as f:
        f.write(html_content)
    logger.info("HTML file 'drone_game.html' created.")

if __name__ == "__main__":
    create_drone_game()
