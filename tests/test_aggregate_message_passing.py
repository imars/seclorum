# tests/test_aggregate_message_passing.py
import pytest
import logging
import sys
import importlib
from unittest.mock import patch, MagicMock
from seclorum.agents.base import Aggregate, AbstractAgent
from seclorum.models import Task, CodeOutput, CodeResult, create_model_manager
from seclorum.models.task import TaskFactory
from typing import Tuple, Any, Optional

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("AggregateMessagePassingTest")

# Store agent flow
agent_flow = []

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

class MockAgent(AbstractAgent):
    """Mock agent to capture message passing."""
    def __init__(self, *args, **kwargs):
        # Avoid real model setup
        self.name = args[0] if args else "mock_agent"
        self.session_id = args[1] if len(args) > 1 else "mock_session"
        self.logger = logging.getLogger(f"MockAgent_{self.name}")
        self.active = False
        self._flow_tracker = []
        logger.debug(f"Instantiating MockAgent: {self.name}")
        agent_flow.append({
            "agent_name": self.name,
            "task_id": args[0] if args else "unknown",
            "session_id": self.session_id,
            "remote": False,
            "status": "instantiated",
            "input": None,
            "output": None
        })

    def process_task(self, task: Task) -> tuple[str, any]:
        use_remote = task.parameters.get("use_remote", False)
        status = "completed"
        # Simulate message passing
        input_data = task.parameters.get("previous_result", "initial")
        # Simulate remote inference if use_remote=True
        result_code = f"processed_by_{self.name}"
        if use_remote:
            result_code = f"remote_processed_by_{self.name}"
        result = CodeOutput(code=result_code, tests=None)

        # Log message passing
        agent_flow.append({
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "status": status,
            "input": input_data,
            "output": result.code
        })
        logger.debug(f"MockAgent Visited {self.name}: task={task.task_id}, input={input_data}, output={result.code}")

        return status, result

class AggregateForTest(Aggregate):
    """Aggregate for testing message passing."""
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id, model_manager)
        self.name = "AggregateForTest"
        logger.debug(f"AggregateForTest initialized: {session_id}")

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"AggregateForTest processing task: {task.task_id}")
        result = None
        status = "failed"

        # Debug agents and graph
        logger.debug(f"Agents: {list(self.agents.keys())}")
        logger.debug(f"Graph: {dict(self.graph)}")

        # Process agents in order, respecting dependencies
        processed = set()
        pending = list(self.agents.keys())
        while pending:
            agent_name = pending[0]  # Simple sequential processing for test
            if agent_name in processed:
                pending.pop(0)
                continue

            # Check dependencies
            deps = self.graph.get(agent_name, [])
            deps_satisfied = True
            for dep_name, condition in deps:
                if dep_name not in processed:
                    deps_satisfied = False
                    break
                # Simple condition check (status == completed)
                if condition and condition.get("status") != "completed":
                    deps_satisfied = False
                    break

            if not deps_satisfied:
                pending.pop(0)
                pending.append(agent_name)  # Retry later
                continue

            agent = self.agents[agent_name]
            logger.debug(f"Processing agent: {agent_name}")
            # Pass previous result as input
            task.parameters["previous_result"] = result.code if result else "initial"
            agent_status, agent_result = agent.process_task(task)
            processed.add(agent_name)
            pending.pop(0)

            if agent_status == "completed" and isinstance(agent_result, CodeOutput):
                result = agent_result
                status = "completed"
            else:
                logger.debug(f"Agent {agent_name} failed: status={agent_status}")
                break

        logger.debug(f"AggregateForTest complete: status={status}, result={result.code if result else None}")
        return status, result

def test_aggregate_two_agents():
    """Test 1 aggregate with 2 agents."""
    agent_flow.clear()
    session_id = "test_aggregate_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create aggregate
    aggregate = AggregateForTest(session_id, model_manager)

    # Create task
    task = TaskFactory.create_code_task(
        description="Test message passing between agents.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=False
    )

    # Patch agents
    try:
        with patch('seclorum.agents.architect.Architect', MockAgent), \
             patch('seclorum.agents.generator.Generator', MockAgent):
            logger.debug("Applying patches for Architect, Generator")
            # Reload modules
            for mod in ['seclorum.agents.architect', 'seclorum.agents.generator']:
                if mod in sys.modules:
                    importlib.reload(sys.modules[mod])
            logger.debug("Reloaded modules: ['seclorum.agents.architect', 'seclorum.agents.generator']")

            # Add agents to aggregate
            from seclorum.agents.architect import Architect
            from seclorum.agents.generator import Generator
            architect = Architect(task.task_id, session_id, model_manager)
            generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
            aggregate.add_agent(architect, [])
            aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])

            # Run pipeline
            logger.debug("Starting AggregateForTest.process_task")
            status, result = aggregate.process_task(task)
            logger.debug(f"Task complete: status={status}")

    finally:
        patch.stopall()

    # Verify flow
    logger.debug(f"Agent flow: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "completed" and a["output"] == f"processed_by_{architect.name}" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "completed" and a["input"] == f"processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code == f"processed_by_{generator.name}", f"Expected final output from Generator, got {result.code}"

def test_aggregate_three_agents():
    """Test 1 aggregate with 3 agents."""
    agent_flow.clear()
    session_id = "test_aggregate_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create aggregate
    aggregate = AggregateForTest(session_id, model_manager)

    # Create task
    task = TaskFactory.create_code_task(
        description="Test message passing between agents.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=False
    )

    # Patch agents
    try:
        with patch('seclorum.agents.architect.Architect', MockAgent), \
             patch('seclorum.agents.generator.Generator', MockAgent), \
             patch('seclorum.agents.tester.Tester', MockAgent):
            logger.debug("Applying patches for Architect, Generator, Tester")
            # Reload modules
            for mod in ['seclorum.agents.architect', 'seclorum.agents.generator', 'seclorum.agents.tester']:
                if mod in sys.modules:
                    importlib.reload(sys.modules[mod])
            logger.debug("Reloaded modules: ['seclorum.agents.architect', 'seclorum.agents.generator', 'seclorum.agents.tester']")

            # Add agents to aggregate
            from seclorum.agents.architect import Architect
            from seclorum.agents.generator import Generator
            from seclorum.agents.tester import Tester
            architect = Architect(task.task_id, session_id, model_manager)
            generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
            tester = Tester(f"{task.task_id}_test", session_id, model_manager)
            aggregate.add_agent(architect, [])
            aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
            aggregate.add_agent(tester, [(generator.name, {"status": "completed"})])

            # Run pipeline
            logger.debug("Starting AggregateForTest.process_task")
            status, result = aggregate.process_task(task)
            logger.debug(f"Task complete: status={status}")

    finally:
        patch.stopall()

    # Verify flow
    logger.debug(f"Agent flow: {agent_flow}")
    assert len(agent_flow) >= 6, f"Expected at least 6 entries (3 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Tester") and a["status"] == "instantiated" for a in agent_flow), "Tester init missing"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "completed" and a["input"] == f"processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
    assert any(a["agent_name"].startswith("Tester") and a["status"] == "completed" and a["input"] == f"processed_by_{generator.name}" for a in agent_flow), "Tester process missing input from Generator"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code == f"processed_by_{tester.name}", f"Expected final output from Tester, got {result.code}"

def test_aggregate_two_agents_remote():
    """Test 1 aggregate with 2 agents using remote inference."""
    agent_flow.clear()
    session_id = "test_aggregate_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create aggregate
    aggregate = AggregateForTest(session_id, model_manager)

    # Create task
    task = TaskFactory.create_code_task(
        description="Test message passing between agents.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=True
    )

    # Patch agents
    try:
        with patch('seclorum.agents.architect.Architect', MockAgent), \
             patch('seclorum.agents.generator.Generator', MockAgent):
            logger.debug("Applying patches for Architect, Generator")
            # Reload modules
            for mod in ['seclorum.agents.architect', 'seclorum.agents.generator']:
                if mod in sys.modules:
                    importlib.reload(sys.modules[mod])
            logger.debug("Reloaded modules: ['seclorum.agents.architect', 'seclorum.agents.generator']")

            # Add agents to aggregate
            from seclorum.agents.architect import Architect
            from seclorum.agents.generator import Generator
            architect = Architect(task.task_id, session_id, model_manager)
            generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
            aggregate.add_agent(architect, [])
            aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])

            # Run pipeline
            logger.debug("Starting AggregateForTest.process_task")
            status, result = aggregate.process_task(task)
            logger.debug(f"Task complete: status={status}")

    finally:
        patch.stopall()

    # Verify flow
    logger.debug(f"Agent flow: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect") and a["status"] == "completed" and a["output"] == f"remote_processed_by_{architect.name}" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator") and a["status"] == "completed" and a["input"] == f"remote_processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code == f"remote_processed_by_{generator.name}", f"Expected final output from Generator, got {result.code}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
