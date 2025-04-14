# tests/test_aggregate_message_passing.py
import pytest
import logging
import sys
import importlib
from unittest.mock import patch
from seclorum.agents.base import Aggregate, AbstractAgent
from seclorum.models import Task, CodeOutput, create_model_manager
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
        try:
            agent_type = kwargs.pop("agent_type", "MockAgent")
            task_id = args[0] if args else "unknown"
            self.name = f"{agent_type}_{task_id}"
            self.session_id = args[1] if len(args) > 1 else "mock_session"
            self.logger = logging.getLogger(f"MockAgent_{self.name}")
            self.active = False
            self._flow_tracker = []
            logger.debug(f"Instantiating MockAgent: {self.name} (args={args}, kwargs={kwargs})")
            agent_flow.append({
                "agent_name": self.name,
                "task_id": task_id,
                "session_id": self.session_id,
                "remote": False,
                "status": "instantiated",
                "input": None,
                "output": None
            })
        except Exception as e:
            logger.error(f"Error instantiating MockAgent: {str(e)}")
            raise

    def process_task(self, task: Task) -> tuple[str, any]:
        try:
            use_remote = task.parameters.get("use_remote", False)
            status = "completed"
            input_data = task.parameters.get("previous_result", "initial")
            result_code = f"processed_by_{self.name}"
            if use_remote:
                result_code = f"remote_processed_by_{self.name}"
            result = CodeOutput(code=result_code, tests=None)

            logger.debug(f"MockAgent Visited {self.name}: task={task.task_id}, input={input_data}, output={result.code}")
            agent_flow.append({
                "agent_name": self.name,
                "task_id": task.task_id,
                "session_id": self.session_id,
                "remote": use_remote,
                "status": status,
                "input": input_data,
                "output": result.code
            })
            return status, result
        except Exception as e:
            logger.error(f"Error in MockAgent.process_task: {str(e)}")
            raise

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

        logger.debug(f"Agents: {list(self.agents.keys())}")
        logger.debug(f"Graph: {dict(self.graph)}")

        processed = set()
        pending = list(self.agents.keys())
        logger.debug(f"Initial pending agents: {pending}")
        while pending:
            agent_name = pending[0]
            logger.debug(f"Checking agent: {agent_name}")
            if agent_name in processed:
                pending.pop(0)
                continue

            deps = self.graph.get(agent_name, [])
            deps_satisfied = True
            for dep_name, condition in deps:
                if dep_name not in processed:
                    logger.debug(f"Dependency {dep_name} not processed for {agent_name}")
                    deps_satisfied = False
                    break
                if condition and condition.get("status") != "completed":
                    logger.debug(f"Condition not met for {dep_name}: {condition}")
                    deps_satisfied = False
                    break

            if not deps_satisfied:
                pending.pop(0)
                pending.append(agent_name)
                continue

            agent = self.agents.get(agent_name)
            if not agent:
                logger.error(f"Agent {agent_name} not found in self.agents")
                break
            logger.debug(f"Processing agent: {agent_name}")
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

    # Patch and instantiate agents
    logger.debug("Starting test_aggregate_two_agents")
    with patch('seclorum.agents.architect.Architect', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Architect", **kwargs)) as architect_patch, \
         patch('seclorum.agents.generator.Generator', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Generator", **kwargs)) as generator_patch:
        logger.debug(f"Patched Architect: {architect_patch}, Generator: {generator_patch}")
        for mod in ['seclorum.agents.architect', 'seclorum.agents.generator']:
            if mod in sys.modules:
                importlib.reload(sys.modules[mod])
                logger.debug(f"Reloaded module: {mod}")

        # Import after patching
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" and a["output"] == f"processed_by_{architect.name}" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["input"] == f"processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
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

    # Patch and instantiate agents
    logger.debug("Starting test_aggregate_three_agents")
    with patch('seclorum.agents.architect.Architect', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Architect", **kwargs)) as architect_patch, \
         patch('seclorum.agents.generator.Generator', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Generator", **kwargs)) as generator_patch, \
         patch('seclorum.agents.tester.Tester', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Tester", **kwargs)) as tester_patch:
        logger.debug(f"Patched Architect: {architect_patch}, Generator: {generator_patch}, Tester: {tester_patch}")
        for mod in ['seclorum.agents.architect', 'seclorum.agents.generator', 'seclorum.agents.tester']:
            if mod in sys.modules:
                importlib.reload(sys.modules[mod])
                logger.debug(f"Reloaded module: {mod}")

        # Import after patching
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        from seclorum.agents.tester import Tester
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        tester = Tester(f"{task.task_id}_test", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}, Tester={tester.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
        aggregate.add_agent(tester, [(generator.name, {"status": "completed"})])

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 6, f"Expected at least 6 entries (3 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), "Tester init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["input"] == f"processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" and a["input"] == f"processed_by_{generator.name}" for a in agent_flow), "Tester process missing input from Generator"
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

    # Patch and instantiate agents
    logger.debug("Starting test_aggregate_two_agents_remote")
    with patch('seclorum.agents.architect.Architect', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Architect", **kwargs)) as architect_patch, \
         patch('seclorum.agents.generator.Generator', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Generator", **kwargs)) as generator_patch:
        logger.debug(f"Patched Architect: {architect_patch}, Generator: {generator_patch}")
        for mod in ['seclorum.agents.architect', 'seclorum.agents.generator']:
            if mod in sys.modules:
                importlib.reload(sys.modules[mod])
                logger.debug(f"Reloaded module: {mod}")

        # Import after patching
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" and a["output"] == f"remote_processed_by_{architect.name}" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["input"] == f"remote_processed_by_{architect.name}" for a in agent_flow), "Generator process missing input from Architect"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code == f"remote_processed_by_{generator.name}", f"Expected final output from Generator, got {result.code}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
