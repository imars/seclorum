# tests/test_agent_flow.py
import pytest
import logging
from unittest.mock import patch
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput, CodeResult, create_model_manager
from seclorum.models.task import TaskFactory
from seclorum.agents.base import AbstractAgent

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger("AgentFlowTest")

# Store agent flow
agent_flow = []

def setup_module():
    """Clear agent flow before tests."""
    logger.debug("Clearing agent_flow")
    agent_flow.clear()

class MockAgent(AbstractAgent):
    """Mock agent to capture flow."""
    def process_task(self, task: Task) -> tuple[str, any]:
        use_remote = task.parameters.get("use_remote", False)
        status = "completed"
        result = CodeOutput(code="mock_code", tests="mock_tests") if "Generator" in self.name else CodeResult(test_code="mock_test", passed=True)

        # Log visit
        agent_flow.append({
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "passed": isinstance(result, CodeResult) and result.passed or bool(result.code.strip()),
            "status": status
        })
        logger.debug(f"Visited {self.name}: task={task.task_id}, remote={use_remote}, passed={isinstance(result, CodeResult) and result.passed or bool(result.code.strip())}")

        return status, result

def test_agent_flow():
    """Test the flow of agents in the Developer pipeline."""
    logger.debug("Starting test_agent_flow")
    session_id = "test_drone_game_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create Developer
    logger.debug("Creating Developer")
    developer = Developer(session_id, model_manager)

    # Mock task
    task = TaskFactory.create_code_task(
        description=(
            "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
            "Drones race across a 3D scrolling landscape of mountains, valleys, flatlands, and obstacles. "
            "Include a scene, camera, lighting, and a drone model. Use the global THREE object from a CDN. "
            "Implement race mechanics with a timer, checkpoints, and win conditions. Include HTML UI for timer, speed, standings, and start/reset buttons."
        ),
        language="javascript",
        generate_tests=True,
        execute=True,
        use_remote=True
    )
    logger.debug(f"Created task: {task.task_id}")

    # Patch log_update, infer, and agents
    with patch.object(AbstractAgent, 'log_update', lambda self, msg: logger.debug(msg)), \
         patch.object(AbstractAgent, 'infer', lambda self, prompt, task, use_remote, **kwargs: (
             '{"pipelines": [{"language": "javascript", "output_file": "drone_game.js"}, {"language": "html", "output_file": "drone_game.html"}]}'
             if "pipelines" in prompt else "mock_plan"
         )), \
         patch('seclorum.agents.architect.Architect', MockAgent), \
         patch('seclorum.agents.developer.Generator', MockAgent), \
         patch('seclorum.agents.developer.Tester', MockAgent), \
         patch('seclorum.agents.developer.Executor', MockAgent), \
         patch('seclorum.agents.developer.Debugger', MockAgent):
        logger.debug("Running developer.process_task")
        status, result = developer.process_task(task)
        logger.debug(f"Pipeline completed with status: {status}")

    # Verify flow
    assert len(agent_flow) > 0, "No agents were visited"
    assert any(agent["agent_name"].startswith("Architect") for agent in agent_flow), "Architect agent missing"
    assert any(agent["agent_name"].startswith("Generator") for agent in agent_flow), "Generator agent missing"
    assert any(agent["agent_name"].startswith("Tester") for agent in agent_flow), "Tester agent missing"
    assert any(agent["agent_name"].startswith("Executor") for agent in agent_flow), "Executor agent missing"

    # Log summary
    logger.info("Agent Flow Summary:")
    for entry in agent_flow:
        logger.info(
            f"Agent: {entry['agent_name']}, Task: {entry['task_id']}, "
            f"Session: {entry['session_id']}, Remote: {entry['remote']}, "
            f"Passed: {entry['passed']}, Status: {entry['status']}"
        )

    # Check status
    assert status == "generated", f"Expected status 'generated', got {status}"

if __name__ == "__main__":
    logger.debug("Running pytest programmatically")
    pytest.main(["-v", __file__])
