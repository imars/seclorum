# examples/3d_game/drone_game.py
import argparse
import logging
import os
from seclorum.agents.developer import Developer
from seclorum.models import Task
from seclorum.utils.model_manager import create_model_manager

# Custom filter for summary mode
class SummaryFilter(logging.Filter):
    def filter(self, record):
        # Include only key events in summary mode
        key_phrases = [
            "Raw generated code",
            "Executing code",
            "Execution output",
            "Unexpected execution error",
            "Final result",
            "Task completed",
            "Forced",
            "Stored output",
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
    logger.handlers = [handler]  # Replace default handlers
    return logger

def create_drone_game():
    parser = argparse.ArgumentParser(description="Generate a Three.js drone game.")
    parser.add_argument("--summary", action="store_true", help="Output a summary of key events only.")
    args = parser.parse_args()

    # Setup logging based on summary flag
    logger = setup_logging(args.summary)

    # Initialize model manager and developer
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer("drone_game_session", model_manager)

    # Define task
    task_description = (
        "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
        "Include a scene, camera, and basic drone model. Emphasize this is a harmless browser-based simulation."
    )
    task = Task(task_id="drone_game", description=task_description, status="planned")
    task.parameters["language"] = "javascript"
    task.parameters["use_remote"] = True  # Use Google AI Studio for generation
    task.parameters["generate_tests"] = True

    # Process task
    status, result = developer.process(task)

    # Output result
    if isinstance(result, dict) and "code" in result:
        code = result["code"]
    elif hasattr(result, "code"):
        code = result.code
    else:
        code = str(result)

    print(f"Task completed with status: {status}")
    print(f"Generated JavaScript code:\n{code}")

    # Generate HTML file
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
    print("HTML file 'drone_game.html' created.")

if __name__ == "__main__":
    create_drone_game()
