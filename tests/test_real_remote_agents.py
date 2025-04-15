# tests/test_real_remote_agents.py
import pytest
import logging
import sys
import json
from unittest.mock import patch, MagicMock
from seclorum.agents.base import Aggregate
from seclorum.models import Task, CodeOutput, create_model_manager
from seclorum.models.task import TaskFactory
from typing import Tuple, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("RealRemoteAgentsTest")

@pytest.fixture(autouse=True)
def clear_modules():
    """Clear seclorum.agents modules to avoid caching."""
    modules_to_clear = [k for k in sys.modules if k.startswith('seclorum.agents')]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)
    logger.debug(f"Cleared modules: {modules_to_clear}")
    yield
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

@pytest.fixture
def model_manager():
    """Provide a model manager for tests."""
    return create_model_manager(provider="ollama", model_name="llama3.2:latest")

@pytest.fixture
def task():
    """Create a code task for remote inference."""
    return TaskFactory.create_code_task(
        description="Generate a 3D drone game design and code.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=True
    )

def test_two_agents_real_remote(model_manager, task):
    """Test 1 aggregate with real Architect and Generator using remote inference."""
    session_id = "test_real_remote_session"

    # Mock remote inference responses
    mock_response_architect = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "design": "drone_game_design",
                        "spec": "3d_movement",
                        "metadata": {"version": 1}
                    })
                }]
            }
        }]
    }
    mock_response_generator = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": """
                    let scene = new THREE.Scene();
                    let camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                    let renderer = new THREE.WebGLRenderer();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    document.body.appendChild(renderer.domElement);
                    let drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
                    scene.add(drone);
                    camera.position.z = 5;
                    function animate() {
                        requestAnimationFrame(animate);
                        drone.rotation.x += 0.01;
                        renderer.render(scene, camera);
                    }
                    animate();
                    """
                }]
            }
        }]
    }

    with patch('requests.post') as mock_post:
        # Configure mock to return different responses based on agent
        def side_effect(url, *args, **kwargs):
            mock = MagicMock()
            prompt = kwargs.get('json', {}).get('contents', [{}])[0].get('parts', [{}])[0].get('text', '')
            if "Architect" in url or "design" in prompt:
                mock.json.return_value = mock_response_architect
            else:
                mock.json.return_value = mock_response_generator
            mock.status_code = 200
            return mock

        mock_post.side_effect = side_effect

        # Create aggregate and agents
        aggregate = Aggregate(session_id, model_manager)
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)

        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "planned"})])

        logger.debug("Starting Aggregate.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}, result_type={type(result).__name__}")

        # Log task parameters for debugging
        logger.debug(f"Task parameters after processing: {task.parameters}")

    # Assertions
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert "scene = new THREE.Scene()" in result.code, "Expected Generator to produce Three.js code"
    assert task.parameters.get(f"result_{architect.name}"), "Architect result missing"
    assert task.parameters.get(f"result_{generator.name}"), "Generator result missing"
    architect_result = task.parameters.get(f"result_{architect.name}")
    assert isinstance(architect_result, CodeOutput), "Architect result should be CodeOutput"
    assert json.loads(architect_result.code).get("design") == "drone_game_design", "Architect design incorrect"
    assert mock_post.called, "Remote inference was not called"
    assert len(mock_post.call_args_list) >= 2, "Expected at least 2 remote calls (Architect, Generator)"

if __name__ == "__main__":
    pytest.main(["-v", __file__])# tests/test_real_remote_agents.py
import pytest
import logging
import sys
import json
from unittest.mock import patch, MagicMock
from seclorum.agents.base import Aggregate
from seclorum.models import Task, CodeOutput, create_model_manager
from seclorum.models.task import TaskFactory
from typing import Tuple, Any

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("RealRemoteAgentsTest")

@pytest.fixture(autouse=True)
def clear_modules():
    """Clear seclorum.agents modules to avoid caching."""
    modules_to_clear = [k for k in sys.modules if k.startswith('seclorum.agents')]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)
    logger.debug(f"Cleared modules: {modules_to_clear}")
    yield
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

@pytest.fixture
def model_manager():
    """Provide a model manager for tests."""
    return create_model_manager(provider="ollama", model_name="llama3.2:latest")

@pytest.fixture
def task():
    """Create a code task for remote inference."""
    return TaskFactory.create_code_task(
        description="Generate a 3D drone game design and code.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=True
    )

def test_two_agents_real_remote(model_manager, task):
    """Test 1 aggregate with real Architect and Generator using remote inference."""
    session_id = "test_real_remote_session"

    # Mock remote inference responses
    mock_response_architect = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "design": "drone_game_design",
                        "spec": "3d_movement",
                        "metadata": {"version": 1}
                    })
                }]
            }
        }]
    }
    mock_response_generator = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": """
                    let scene = new THREE.Scene();
                    let camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
                    let renderer = new THREE.WebGLRenderer();
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    document.body.appendChild(renderer.domElement);
                    let drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
                    scene.add(drone);
                    camera.position.z = 5;
                    function animate() {
                        requestAnimationFrame(animate);
                        drone.rotation.x += 0.01;
                        renderer.render(scene, camera);
                    }
                    animate();
                    """
                }]
            }
        }]
    }

    with patch('requests.post') as mock_post:
        # Configure mock to return different responses based on agent
        def side_effect(url, *args, **kwargs):
            mock = MagicMock()
            if "Architect" in url or "design" in kwargs.get('json', {}).get('contents', [{}])[0].get('parts', [{}])[0].get('text', ''):
                mock.json.return_value = mock_response_architect
            else:
                mock.json.return_value = mock_response_generator
            mock.status_code = 200
            return mock

        mock_post.side_effect = side_effect

        # Create aggregate and agents
        aggregate = Aggregate(session_id, model_manager)
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)

        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])

        logger.debug("Starting Aggregate.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    # Assertions
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert "scene = new THREE.Scene()" in result.code, "Expected Generator to produce Three.js code"
    assert task.parameters.get(f"result_{architect.name}"), "Architect result missing"
    assert task.parameters.get(f"result_{generator.name}"), "Generator result missing"
    architect_result = task.parameters.get(f"result_{architect.name}")
    assert isinstance(architect_result, CodeOutput), "Architect result should be CodeOutput"
    assert json.loads(architect_result.code).get("design") == "drone_game_design", "Architect design incorrect"
    assert mock_post.called, "Remote inference was not called"
    assert len(mock_post.call_args_list) >= 2, "Expected at least 2 remote calls (Architect, Generator)"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
