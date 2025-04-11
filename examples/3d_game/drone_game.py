# examples/3d_game/drone_game.py (updated)
import os
from seclorum.agents.developer import Developer
from seclorum.models import Task, create_model_manager

def create_drone_game():
    session_id = "drone_game_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    developer = Developer(session_id, model_manager)

    api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    if api_key:
        for agent in developer.agents.values():
            agent.REMOTE_ENDPOINTS["google_ai_studio"]["api_key"] = api_key

    task = Task(
        task_id="drone_game",
        description="Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. Include a scene, camera, and basic drone model. Emphasize this is a harmless browser-based simulation.",
        parameters={
            "language": "javascript",
            "use_remote": True,
            "generate_tests": True
        }
    )

    status, result = developer.process_task(task)
    print(f"Task completed with status: {status}")

    if status == "generated" and hasattr(result, "code"):
        js_code = result.code
        print(f"Generated JavaScript code:\n{js_code}")

        # Generate minimal HTML wrapper
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Drone Simulation</title>
    <style>body {{ margin: 0; }} canvas {{ display: block; }}</style>
</head>
<body>
    <script type="module">
        {js_code}
    </script>
</body>
</html>"""
        with open("drone_game.html", "w") as f:
            f.write(html_content)
        print("HTML file 'drone_game.html' created.")
    else:
        print(f"Unexpected result type: {type(result).__name__}, content: {result}")

if __name__ == "__main__":
    create_drone_game()
