# examples/3d_game/drone_game.py
import argparse[ ... ]  # Keep existing imports

def create_drone_game():
    parser = argparse.ArgumentParser(description="Generate a Three.js drone game.")
    parser.add_argument("--summary", action="store_true", help="Output a summary of key events only.")
    args = parser.parse_args()

    logger = setup_logging(args.summary)
    logger.info(f"Running from: {os.getcwd()}")

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

    status, result = developer.process_task(task)

    # Ensure result is a CodeOutput with valid code
    if isinstance(result, CodeOutput) and result.code.strip():
        # Clean up Node.js-specific require statements
        code = re.sub(r"const THREE = require\('three'\);\n?", "", result.code).strip()
        tests = result.tests.strip() if result.tests else None
    else:
        code = "No valid code generated"
        tests = None
        logger.error(f"Final result invalid: {result}")

    logger.info(f"Task completed with status: {status}")
    logger.info(f"Raw generated code:\n{code}")
    if tests:
        logger.info(f"Generated tests:\n{tests}")

    # Save the JavaScript code to drone_game.js
    js_path = "drone_game.js"  # Relative path since we're in examples/3d_game
    with open(js_path, "w") as f:
        f.write(code)
    logger.info(f"JavaScript file '{js_path}' created, size: {os.path.getsize(js_path)} bytes")

    # Save tests if generated
    if tests:
        test_path = "drone_game.test.js"
        with open(test_path, "w") as f:
            f.write(tests)
        logger.info(f"Test file '{test_path}' created, size: {os.path.getsize(test_path)} bytes")

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
    <script src="drone_game.js"></script>
</body>
</html>
    """
    html_path = "drone_game.html"
    with open(html_path, "w") as f:
        f.write(html_content)
    logger.info(f"HTML file '{html_path}' created, size: {os.path.getsize(html_path)} bytes")
    logger.info(f"Run 'open {html_path}' to view the game in a browser.")

if __name__ == "__main__":
    create_drone_game()
