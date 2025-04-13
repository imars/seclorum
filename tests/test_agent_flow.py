# tests/test_agent_flow.py
import pytest
import logging
from unittest.mock import patch
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput, TestResult, CodeResult, create_model_manager
from seclorum.models.task import TaskFactory
from seclorum.agents.base import AbstractAgent

# Configure minimal logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AgentFlowTest")

# Store agent flow for verification
agent_flow = []

def setup_module():
    """Clear agent flow before tests."""
    agent_flow.clear()

class MockAgent(AbstractAgent):
    """Mock agent to capture flow without executing real tasks."""
    def process_task(self, task: Task) -> tuple[str, any]:
        use_remote = task.parameters.get("use_remote", False)
        status = "completed"
        if "Generator" in self.name:
            result = CodeOutput(code="mock_code", tests="mock_tests")
        elif "Tester" in self.name:
            result = TestResult(test_code="mock_test", passed=True)
        elif "Architect" in self.name:
            result = "mock_plan"  # Architect returns a plan (str)
        else:
            result = CodeResult(test_code="mock_test", passed=True)

        # Log agent visit
        agent_flow.append({
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "passed": isinstance(result, (TestResult, CodeResult)) and result.passed or bool(result),
            "status": status
        })
        logger.debug(f"Visited {self.name}: task={task.task_id}, remote={use_remote}, passed={isinstance(result, (TestResult, CodeResult)) and result.passed or bool(result)}")

        return status, result

def test_agent_flow():
    """Test the flow of agents in the Developer pipeline."""
    session_id = "test_drone_game_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create Developer with mocked logging
    developer = Developer(session_id, model_manager)

    # Mock task similar to drone_game.py
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

    # Patch log_update and agent classes
    with patch.object(AbstractAgent, 'log_update', lambda self, msg: logger.debug(msg)):
        with patch('seclorum.agents.architect.Architect', MockAgent), \
             patch('seclorum.agents.generator.Generator', MockAgent), \
             patch('seclorum.agents.tester.Tester', MockAgent), \
             patch('seclorum.agents.executor.Executor', MockAgent), \
             patch('seclorum.agents.debugger.Debugger', MockAgent):
            # Run the pipeline
            status, result = developer.process_task(task)

    # Verify agent flow
    assert len(agent_flow) > 0, "No agents were visited"
    assert any(agent["agent_name"].startswith("Architect") for agent in agent_flow), "Architect agent missing"
    assert any(agent["agent_name"].startswith("Generator") for agent in agent_flow), "Generator agent missing"
    assert any(agent["agent_name"].startswith("Tester") for agent in agent_flow), "Tester agent missing"
    assert any(agent["agent_name"].startswith("Executor") for agent in agent_flow), "Executor agent missing"

    # Log flow summary
    logger.info("Agent Flow Summary:")
    for entry in agent_flow:
        logger.info(
            f"Agent: {entry['agent_name']}, Task: {entry['task_id']}, "
            f"Session: {entry['session_id']}, Remote: {entry['remote']}, "
            f"Passed: {entry['passed']}, Status: {entry['status']}"
        )

    # Check final status
    assert status == "generated", f"Expected status 'generated', got {status}"
