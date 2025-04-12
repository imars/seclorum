# tests/test_drone_game.py
import subprocess
import os
import pytest
from seclorum.models import Task, CodeOutput
from seclorum.agents.developer import Developer
from seclorum.agents.tester import Tester
from seclorum.models import create_model_manager

@pytest.fixture
def setup_drone_game(tmp_path):
    """Set up a temporary environment for testing drone_game.py."""
    # Copy drone_game.py to tmp_path
    src = "examples/3d_game/drone_game.py"
    dst = tmp_path / "drone_game.py"
    with open(src, "r") as f:
        dst.write_text(f.read())

    # Create examples/3d_game directory
    game_dir = tmp_path / "examples" / "3d_game"
    game_dir.mkdir(parents=True, exist_ok=True)

    # Change to tmp_path for execution
    os.chdir(tmp_path)
    yield tmp_path
    # Cleanup handled by tmp_path fixture

def test_drone_game_generation(setup_drone_game):
    """Test that drone_game.py generates drone_game.js and drone_game.html."""
    # Run drone_game.py
    result = subprocess.run(["python", "drone_game.py"], capture_output=True, text=True)
    assert result.returncode == 0, f"drone_game.py failed: {result.stderr}"

    # Check if files were created
    js_path = setup_drone_game / "examples/3d_game/drone_game.js"
    html_path = setup_drone_game / "examples/3d_game/drone_game.html"
    assert js_path.exists(), "drone_game.js was not created"
    assert html_path.exists(), "drone_game.html was not created"

    # Verify drone_game.js content
    with open(js_path, "r") as f:
        js_content = f.read()
    assert "THREE.Scene" in js_content, "drone_game.js does not contain expected Three.js scene setup"
    assert "requestAnimationFrame" in js_content, "drone_game.js lacks animation loop"

def test_drone_game_tester(setup_drone_game):
    """Test Tester agent generates valid test code for drone_game.js."""
    # Run drone_game.py to generate drone_game.js
    subprocess.run(["python", "drone_game.py"], check=True)

    # Set up Developer and Tester
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")
    session_id = "drone_game_test_session"
    developer = Developer(session_id, model_manager)
    tester = Tester("drone_game", session_id, model_manager)

    # Create task with generated code
    js_path = setup_drone_game / "examples/3d_game/drone_game.js"
    with open(js_path, "r") as f:
        code = f.read()
    task = Task(
        task_id="drone_game_test",
        description="Test Three.js drone game",
        parameters={
            "language": "javascript",
            "generate_tests": True,
            "Generator_dev_task": {"status": "generated", "result": CodeOutput(code=code, tests=None)}
        }
    )

    # Run Tester
    status, result = tester.process_task(task)
    assert status == "tested", f"Tester failed with status: {status}"
    assert result.test_code, "Tester did not generate test code"
    assert "describe(" in result.test_code, "Test code lacks Jest describe block"
    assert result.passed is False, "Tester should not mark tests as passed without execution"

def test_drone_game_execution(setup_drone_game):
    """Test drone_game.js execution using Puppeteer."""
    # Ensure drone_game.js exists
    subprocess.run(["python", "drone_game.py"], check=True)

    js_path = setup_drone_game / "examples/3d_game/drone_game.js"
    assert js_path.exists(), "drone_game.js was not created"

    # Run Puppeteer test
    puppeteer_script = "seclorum/scripts/run_puppeteer.js"
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

if __name__ == "__main__":
    pytest.main(["-v", __file__])
