# tests/test_agent_flow.py
import pytest
import logging
from unittest.mock import patch, MagicMock
from seclorum.agents.developer import Developer
from seclorum.models import Task, CodeOutput, CodeResult, create_model_manager
from seclorum.models.task import TaskFactory
from seclorum.agents.base import AbstractAgent

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("AgentFlowTest")

# Store agent flow
agent_flow = []

def setup_module():
    """Clear agent flow before tests."""
    agent_flow.clear()

class MockAgent(AbstractAgent):
    """Mock agent to capture flow."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.debug(f"Instantiating MockAgent: {self.name}")
        agent_flow.append({
            "agent_name": self.name,
            "task_id": args[0] if args else "unknown",
            "session_id": self.session_id,
            "remote": False,
            "passed": True,
            "status": "instantiated",
            "language": kwargs.get("language", "")
        })

    def process_task(self, task: Task) -> tuple[str, any]:
        use_remote = task.parameters.get("use_remote", False)
        language = task.parameters.get("language", "")
        status = "completed"
        result = CodeOutput(code="mock_code", tests="mock_tests") if "Generator" in self.name else \
                 CodeResult(test_code="mock_test", passed=True, code="mock_code") if "Tester" in self.name else \
                 CodeOutput(code="mock_code", tests=None)

        # Log visit
        agent_flow.append({
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "passed": isinstance(result, CodeResult) and result.passed or bool(result.code.strip()),
            "status": status,
            "language": language
        })
        logger.debug(f"MockAgent Visited {self.name}: task={task.task_id}, language={language}, remote={use_remote}, "
                     f"passed={isinstance(result, CodeResult) and result.passed or bool(result.code.strip())}")

        return status, result

def test_agent_flow():
    """Test the flow of agents in the Developer pipeline."""
    session_id = "test_drone_game_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create Developer
    developer = Developer(session_id, model_manager)
    logger.debug("Developer instantiated")

    # Create tasks for JavaScript and HTML
    js_task = TaskFactory.create_code_task(
        description=(
            "Create a Three.js JavaScript game with a virtual flying drone controlled by arrow keys in a 3D scene. "
            "Drones race across a 3D scrolling landscape of mountains, valleys, flatlands, and obstacles. "
            "Include a scene, camera, lighting, and a drone model. Use the global THREE object from a CDN. "
            "Implement race mechanics with a timer, checkpoints, and win conditions."
        ),
        language="javascript",
        generate_tests=True,
        execute=True,
        use_remote=True
    )
    js_task.parameters["output_file"] = "drone_game.js"

    html_task = TaskFactory.create_code_task(
        description=(
            "Create an HTML file for a Three.js drone racing game with a canvas, UI for timer, speed, standings, "
            "and start/reset buttons. Include Three.js CDN and link to drone_game.js."
        ),
        language="html",
        generate_tests=True,
        execute=True,
        use_remote=True
    )
    html_task.parameters["output_file"] = "drone_game.html"

    # Mock infer to return pipelines
    mock_infer = MagicMock(side_effect=lambda prompt, *args, **kwargs: (
        '{"pipelines": [{"language": "javascript", "output_file": "drone_game.js"}, {"language": "html", "output_file": "drone_game.html"}]}'
        if "pipelines" in prompt else "mock_plan"
    ))

    # Patch agents in correct namespaces
    with patch('seclorum.agents.base.AbstractAgent.log_update', lambda self, msg: logger.debug(f"Patched log: {msg}")), \
         patch('seclorum.agents.base.AbstractAgent.infer', mock_infer), \
         patch('seclorum.agents.architect.Architect', MockAgent), \
         patch('seclorum.agents.generator.Generator', MockAgent), \
         patch('seclorum.agents.tester.Tester', MockAgent), \
         patch('seclorum.agents.executor.Executor', MockAgent), \
         patch('seclorum.agents.debugger.Debugger', MockAgent):
        logger.debug("Applying patches for agent classes")
        # Run pipeline for both tasks
        logger.debug("Starting Developer.process_task for js_task")
        status_js, result_js = developer.process_task(js_task)
        logger.debug(f"js_task complete: status={status_js}")
        logger.debug("Starting Developer.process_task for html_task")
        status_html, result_html = developer.process_task(html_task)
        logger.debug(f"html_task complete: status={status_html}")

    # Verify flow
    logger.debug(f"Agent flow: {agent_flow}")
    assert len(agent_flow) >= 10, f"Expected at least 10 agent visits (5 per pipeline), got {len(agent_flow)}: {agent_flow}"
    assert any(agent["agent_name"].startswith("Architect") and agent["language"] == "javascript" for agent in agent_flow), "Architect missing for JavaScript"
    assert any(agent["agent_name"].startswith("Architect") and agent["language"] == "html" for agent in agent_flow), "Architect missing for HTML"
    assert sum(agent["agent_name"].startswith("Generator") and agent["language"] == "javascript" for agent in agent_flow) >= 1, "Generator missing for JavaScript"
    assert sum(agent["agent_name"].startswith("Generator") and agent["language"] == "html" for agent in agent_flow) >= 1, "Generator missing for HTML"
    assert any(agent["agent_name"].startswith("Tester") and agent["language"] == "javascript" for agent in agent_flow), "Tester missing for JavaScript"
    assert any(agent["agent_name"].startswith("Tester") and agent["language"] == "html" for agent in agent_flow), "Tester missing for HTML"
    assert any(agent["agent_name"].startswith("Executor") for agent in agent_flow), "Executor missing"
    assert any(agent["agent_name"].startswith("Debugger") for agent in agent_flow), "Debugger missing"

    # Log summary
    logger.info("Agent Flow Summary:")
    for entry in agent_flow:
        logger.info(
            f"Agent: {entry['agent_name']}, Task: {entry['task_id']}, "
            f"Session: {entry['session_id']}, Language: {entry['language']}, "
            f"Remote: {entry['remote']}, Passed: {entry['passed']}, Status: {entry['status']}"
        )

    # Check status
    assert status_js == "generated", f"Expected JavaScript status 'generated', got {status_js}"
    assert status_html == "generated", f"Expected HTML status 'generated', got {status_html}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
