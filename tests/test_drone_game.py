# tests/test_drone_game.py
import subprocess
import os
import pytest
import unittest
from pathlib import Path
from seclorum.models import Task
from seclorum.agents.developer import Developer
from seclorum.models import create_model_manager

# Get project root (assuming tests/ is in project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class TestDroneGame(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def setup_drone_game(self, tmp_path):
        """Set up a temporary environment for testing drone_game.py."""
        # Create examples/3d_game structure in tmp_path
        examples_dir = tmp_path / "examples/3d_game"
        examples_dir.mkdir(parents=True)

        # Copy drone_game.py to tmp_path/examples/3d_game
        src = PROJECT_ROOT / "examples/3d_game/drone_game.py"
        dst = examples_dir / "drone_game.py"
        dst.write_text(src.read_text())

        # Copy seclorum package to tmp_path for imports
        seclorum_src = PROJECT_ROOT / "seclorum"
        seclorum_dst = tmp_path / "seclorum"
        import shutil
        shutil.copytree(seclorum_src, seclorum_dst, dirs_exist_ok=True)

        # Initialize a Git repo in examples/3d_game for FileSystemManager
        subprocess.run(["git", "init"], cwd=examples_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial commit"], cwd=examples_dir, check=True, capture_output=True)

        # Change to examples/3d_game for execution
        self.original_dir = os.getcwd()
        os.chdir(examples_dir)
        self.tmp_path = tmp_path
        yield tmp_path
        os.chdir(self.original_dir)

    def test_drone_game_generation(self):
        """Test that drone_game.py generates drone_game.js and drone_game.html."""
        # Run drone_game.py from examples/3d_game
        result = subprocess.run(
            ["python", "drone_game.py"],
            capture_output=True,
            text=True,
            cwd=self.tmp_path / "examples/3d_game"
        )
        self.assertEqual(result.returncode, 0, f"drone_game.py failed: {result.stderr}")

        # Check if files were created
        js_path = self.tmp_path / "examples/3d_game/drone_game.js"
        html_path = self.tmp_path / "examples/3d_game/drone_game.html"
        test_path = self.tmp_path / "examples/3d_game/drone_game.test.js"
        self.assertTrue(js_path.exists(), "drone_game.js was not created")
        self.assertTrue(html_path.exists(), "drone_game.html was not created")
        self.assertTrue(test_path.exists(), "drone_game.test.js was not created")

        # Verify drone_game.js content
        js_content = js_path.read_text()
        self.assertIn("THREE.Scene", js_content, "drone_game.js does not contain expected Three.js scene setup")
        self.assertNotIn("require('three')", js_content, "drone_game.js contains Node.js require statement")

    def test_drone_game_execution(self):
        """Test drone_game.js execution using Puppeteer."""
        # Ensure drone_game.js exists by running drone_game.py
        subprocess.run(
            ["python", "drone_game.py"],
            check=True,
            cwd=self.tmp_path / "examples/3d_game"
        )

        js_path = self.tmp_path / "examples/3d_game/drone_game.js"
        self.assertTrue(js_path.exists(), "drone_game.js was not created before execution test")

        # Run Puppeteer test
        puppeteer_script = PROJECT_ROOT / "seclorum/scripts/run_puppeteer.js"
        result = subprocess.run(
            ["node", str(puppeteer_script), str(js_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, f"Puppeteer test failed: {result.stderr}")

        # Check Puppeteer output
        output_path = self.tmp_path / "examples/3d_game/drone_game.js.out"
        self.assertTrue(output_path.exists(), "Puppeteer output file was not created")
        output = output_path.read_text()
        self.assertIn("Execution successful", output, "Puppeteer did not detect scene or animation")

    def test_drone_game_developer(self):
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
        task.parameters["execute"] = True

        status, result = developer.process_task(task)
        self.assertEqual(status, "tested", f"Expected status 'tested', got '{status}'")
        self.assertIsInstance(result, TestResult, f"Expected TestResult, got {type(result).__name__}")
        self.assertTrue(result.passed, f"Developer tests failed: {result.output}")

if __name__ == "__main__":
    unittest.main()
