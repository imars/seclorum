# examples/3d_game/drone_game.py
from seclorum.models.task import Task
from seclorum.agents.developer import Developer
from seclorum.models.manager import create_model_manager

def create_drone_game():
    session_id = "drone_game_session"
    model_manager = create_model_manager(provider="ollama", model_name="codellama")
    developer = Developer(session_id, model_manager)

    task = Task(
        task_id="drone_game",
        description="Create a Three.js game with a flying drone controlled by arrow keys. Include a scene, camera, and basic drone model.",
        parameters={
            "language": "javascript",
            "generate_tests": True
        }
    )

    status, result = developer.process_task(task)
    print(f"Task completed with status: {status}")
    print(f"Generated JavaScript code:\n{result.code}")
    if result.tests:
        print(f"Generated Jest tests:\n{result.tests}")

    # Write to files
    with open("examples/3d_game/drone_game.js", "w") as f:
        f.write(result.code)
    if result.tests:
        with open("examples/3d_game/drone_game.test.js", "w") as f:
            f.write(result.tests)

    # Basic HTML wrapper
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Flying Drone Game</title>
    <style>body {{ margin: 0; }} canvas {{ width: 100%; height: 100%; }}</style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js"></script>
</head>
<body>
    <script src="drone_game.js"></script>
</body>
</html>
    """
    with open("examples/3d_game/index.html", "w") as f:
        f.write(html_content)

if __name__ == "__main__":
    create_drone_game()
