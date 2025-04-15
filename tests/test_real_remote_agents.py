# tests/test_real_remote_agents.py
import pytest
import logging
import sys
import json
from unittest.mock import patch, MagicMock
from seclorum.agents.base import Aggregate
from seclorum.models import Task, CodeOutput, CodeResult, create_model_manager
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
        generate_tests=True,
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
                    let renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('myCanvas') });
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    let drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
                    scene.add(drone);
                    camera.position.z = 5;
                    document.addEventListener('keydown', function(event) {
                        if (event.key === 'ArrowUp') drone.position.y += 0.1;
                    });
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
            if "Architect" in prompt or "design" in prompt:
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
        logger.debug(f"Task parameters: {task.parameters}")

    # Assertions
    assert status == "generated", f"Expected status 'generated', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert "scene = new THREE.Scene()" in result.code, "Expected Generator to produce Three.js code"
    assert task.parameters.get(f"{architect.name}"), "Architect result missing"
    assert task.parameters.get(f"{generator.name}"), "Generator result missing"
    architect_result = task.parameters.get(f"{architect.name}")
    assert isinstance(architect_result, dict) and "result" in architect_result, "Architect result malformed"
    assert json.loads(architect_result["result"].code).get("design") == "drone_game_design", "Architect design incorrect"
    assert mock_post.called, "Remote inference was not called"
    assert len(mock_post.call_args_list) >= 2, "Expected at least 2 remote calls"

def test_aggregate_message_passing(model_manager, task):
    """Test message passing with real Architect, Generator, and Tester using mocked remote inference."""
    session_id = "test_message_passing_session"

    # Mock remote inference responses
    mock_response_architect = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": json.dumps({
                        "design": "drone_game_design",
                        "spec": "3d_movement_with_controls",
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
                    let renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('myCanvas') });
                    renderer.setSize(window.innerWidth, window.innerHeight);
                    let drone = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial({ color: 0xff0000 }));
                    scene.add(drone);
                    camera.position.z = 5;
                    document.addEventListener('keydown', function(event) {
                        if (event.key === 'ArrowUp') drone.position.y += 0.1;
                        if (event.key === 'ArrowDown') drone.position.y -= 0.1;
                    });
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
    mock_response_tester = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": """
                    describe('Drone Game', () => {
                        test('Scene is initialized', () => {
                            expect(scene).toBeDefined();
                        });
                        test('Drone moves up on ArrowUp', () => {
                            const event = new KeyboardEvent('keydown', { key: 'ArrowUp' });
                            document.dispatchEvent(event);
                            expect(drone.position.y).toBeGreaterThan(0);
                        });
                    });
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
            if "Architect" in prompt or "design" in prompt:
                mock.json.return_value = mock_response_architect
            elif "test" in prompt.lower():
                mock.json.return_value = mock_response_tester
            else:
                mock.json.return_value = mock_response_generator
            mock.status_code = 200
            return mock

        mock_post.side_effect = side_effect

        # Create aggregate and agents
        aggregate = Aggregate(session_id, model_manager)
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        from seclorum.agents.tester import Tester
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        tester = Tester(f"{task.task_id}_test", session_id, model_manager)

        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}, Tester={tester.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "planned"})])
        aggregate.add_agent(tester, [(generator.name, {"status": "generated"})])

        logger.debug("Starting Aggregate.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}, result_type={type(result).__name__}")
        logger.debug(f"Task parameters: {task.parameters}")

    # Assertions
    assert status == "tested", f"Expected status 'tested', got {status}"
    assert isinstance(result, CodeResult), f"Expected CodeResult, got {type(result)}"
    assert "scene" in result.test_code, "Expected Tester to produce Jest tests"
    assert task.parameters.get(f"{architect.name}"), "Architect result missing"
    assert task.parameters.get(f"{generator.name}"), "Generator result missing"
    assert task.parameters.get(f"{tester.name}"), "Tester result missing"
    architect_result = task.parameters.get(f"{architect.name}")
    assert isinstance(architect_result, dict) and "result" in architect_result, "Architect result malformed"
    assert json.loads(architect_result["result"].code).get("design") == "drone_game_design", "Architect design incorrect"
    generator_result = task.parameters.get(f"{generator.name}")
    assert isinstance(generator_result, dict) and "result" in generator_result, "Generator result malformed"
    assert "scene = new THREE.Scene()" in generator_result["result"].code, "Generator code incorrect"
    tester_result = task.parameters.get(f"{tester.name}")
    assert isinstance(tester_result, dict) and "result" in tester_result, "Tester result malformed"
    assert tester_result["result"].passed, "Tester should pass"
    assert mock_post.called, "Remote inference was not called"
    assert len(mock_post.call_args_list) >= 3, "Expected at least 3 remote calls"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
