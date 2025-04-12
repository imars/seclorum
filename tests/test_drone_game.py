# tests/test_drone_game.py
import subprocess
import os
import pytest
from unittest.mock import patch
from seclorum.models import Task
from seclorum.agents.developer import Developer
from seclorum.models import create_model_manager

# Get the project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

@pytest.fixture
def setup_drone_game(tmp_path):
    """Set up a temporary environment for testing drone_game.py."""
    # Copy drone_game.py to tmp_path
    src = os.path.join(PROJECT_ROOT, "examples", "3d_game", "drone_game.py")
    dst = tmp_path / "drone_game.py"
    with open(src, "r") as f:
        dst.write_text(f.read())

    # Create a minimal Git repository to satisfy FileSystemManager
    os.makedirs(tmp_path / ".git", exist_ok=True)
    with open(tmp_path / ".git" / "config", "w") as f:
        f.write("[core]\nrepositoryformatversion = 0\n")

    # Change to tmp_path for execution
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(original_cwd)

def test_drone_game_generation(setup_drone_game):
    """Test that drone_game.py generates drone_game.js and drone_game.html."""
    # Run drone_game.py
    result = subprocess.run(["python", "drone_game.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"drone_game.py failed: {result.stderr}"

    # Check if files were created
    js_path = setup_drone_game / "examples/3d_game/drone_game.js"
    html_path = setup_drone_game / "examples/3d_game/drone_game.html"
    test_path = setup_drone_game / "examples/3d_game/drone_game.test.js"
    assert js_path.exists(), "drone_game.js was not created"
    assert html_path.exists(), "drone_game.html was not created"
    assert test_path.exists(), "drone_game.test.js was not created"

    # Verify drone_game.js content
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "THREE.Scene" in js_content, "drone_game.js does not contain expected Three.js scene setup"
    assert "require('three')" not in js_content, "drone_game.js contains Node.js require statement"

def test_drone_game_execution(setup_drone_game):
    """Test drone_game.js execution using Puppeteer."""
    # Ensure drone_game.js exists by running drone_game.py
    subprocess.run(["python", "drone_game.py"], check=True)

    js_path = setup_drone_game / "examples/3d_game/drone_game.js"
    assert js_path.exists(), "drone_game.js was not created before execution test"

    # Run Puppeteer test
    puppeteer_script = os.path.join(PROJECT_ROOT, "seclorum", "scripts", "run_puppeteer.js")
    result = subprocess.run(
        ["node", puppeteer_script, str(js_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Puppeteer test failed: {result.stderr}"

    # Check Puppeteer output
    output_path = setup_drone_game / "examples/3d_game/drone_game.js.out"
    assert output_path.exists(), "Puppeteer output file was not created"
    with open(output_path, "r") as f:
        output = f.read()
    assert "Execution successful" in output, "Puppeteer did not detect scene or animation"

def test_drone_game_developer(setup_drone_game):
    """Test Developer agent pipeline for drone game."""
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

    status, result = developer.process_task(task)
    assert status == "tested", f"Expected status 'tested', got '{status}'"
    assert result.passed, f"Developer tests failed: {result.output}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
