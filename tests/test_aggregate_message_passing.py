# tests/test_aggregate_message_passing.py
import pytest
import logging
import sys
import importlib
import json
from unittest.mock import patch, MagicMock
from seclorum.agents.base import Aggregate, AbstractAgent
from seclorum.models import Task, CodeOutput, create_model_manager
from seclorum.models.task import TaskFactory
from typing import Tuple, Any, Optional, Union

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

@pytest.fixture
def model_manager():
    """Provide a model manager for tests."""
    return create_model_manager(provider="ollama", model_name="llama3.2:latest")

@pytest.fixture
def task():
    """Create a code task for testing."""
    return TaskFactory.create_code_task(
        description="Generate a 3D drone game design and code.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=True
    )

class MockAgent:
    """Mock agent to capture message passing, avoiding AbstractAgent."""
    def __init__(self, *args, **kwargs):
        try:
            agent_type = kwargs.pop("agent_type", "MockAgent")
            task_id = args[0] if args else "unknown"
            self.name = f"{agent_type}_{task_id}"
            self.session_id = args[1] if len(args) > 1 else "mock_session"
            self.logger = logging.getLogger(f"MockAgent_{self.name}")
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

    def process_task(self, task: Task) -> Tuple[str, Any]:
        try:
            use_remote = task.parameters.get("use_remote", False)
            status = "completed"
            input_data = task.parameters.get("previous_result", "initial")

            # Handle inputs
            if isinstance(input_data, CodeOutput):
                input_data = input_data.code
            input_value = input_data
            logger.debug(f"Processing {self.name} with input: {input_value}")

            # Handle complex outputs
            if self.name.startswith("Architect_"):
                complex_output = {
                    "design": f"design_by_{self.name}",
                    "spec": f"spec_by_{self.name}",
                    "metadata": {"version": 1}
                }
                result_code = json.dumps(complex_output)
            elif self.name.startswith("Generator_"):
                try:
                    parsed_input = json.loads(input_data) if isinstance(input_data, str) else input_data
                    input_value = parsed_input.get("design", "unknown") if isinstance(parsed_input, dict) else input_data
                except json.JSONDecodeError:
                    input_value = input_data
                result_code = f"generated_from_design_by_{self.name}"
            elif self.name.startswith("Debugger_"):
                try:
                    parsed_input = json.loads(input_data) if isinstance(input_data, str) else input_data
                    input_value = parsed_input.get("spec", "unknown") if isinstance(parsed_input, dict) else input_data
                except json.JSONDecodeError:
                    input_value = input_data
                result_code = f"debugged_from_spec_by_{self.name}"
            elif self.name.startswith("Tester_") or self.name.startswith("Executor_"):
                result_code = f"processed_{input_value}"
            else:
                result_code = f"processed_by_{self.name}"

            if use_remote and not self.name.startswith("Architect_"):
                result_code = f"remote_{result_code}"
            result = CodeOutput(code=result_code, tests=None)

            logger.debug(f"MockAgent Visited {self.name}: task={task.task_id}, input={input_data}, output={result_code}")
            agent_flow.append({
                "agent_name": self.name,
                "task_id": task.task_id,
                "session_id": self.session_id,
                "remote": use_remote,
                "status": status,
                "input": input_data,
                "output": result_code
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
        max_iterations = len(self.agents) * 2
        iteration = 0

        while pending and iteration < max_iterations:
            iteration += 1
            agent_name = pending[0]
            logger.debug(f"Iteration {iteration}: Checking agent: {agent_name}")
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
                if condition and condition.get("status") == "completed":
                    dep_status = task.parameters.get(f"status_{dep_name}")
                    if dep_status != "completed":
                        logger.debug(f"Condition not met for {dep_name}: {condition}, status={dep_status}")
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
            # Set previous_result to the output of the agent's dependency
            deps = self.graph.get(agent_name, [])
            if deps:
                dep_name = deps[0][0]  # Use first dependency
                dep_result = task.parameters.get(f"result_{dep_name}")
                task.parameters["previous_result"] = dep_result.code if dep_result else "initial"
            else:
                task.parameters["previous_result"] = "initial"

            try:
                agent_status, agent_result = agent.process_task(task)
                task.parameters[f"result_{agent_name}"] = agent_result
                task.parameters[f"status_{agent_name}"] = agent_status
            except Exception as e:
                logger.error(f"Error processing agent {agent_name}: {str(e)}")
                status = "failed"
                break
            processed.add(agent_name)
            pending.pop(0)
            logger.debug(f"Processed agents: {processed}")

            if agent_status == "completed" and isinstance(agent_result, CodeOutput):
                result = agent_result
                status = "completed"
            else:
                logger.debug(f"Agent {agent_name} failed: status={agent_status}")
                status = "failed"
                break

        if not processed:
            logger.error("No agents were processed")
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
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
        logger.debug(f"Agent flow after agent creation: {agent_flow}")
        assert len(agent_flow) >= 2, f"Expected at least 2 init entries, got {len(agent_flow)}: {agent_flow}"

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), "Generator process missing"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("generated_from_"), f"Expected Generator output, got {result.code}"

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
        logger.debug(f"Agent flow after agent creation: {agent_flow}")
        assert len(agent_flow) >= 3, f"Expected at least 3 init entries, got {len(agent_flow)}: {agent_flow}"

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 6, f"Expected at least 6 entries (3 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), "Tester init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), "Generator process missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" for a in agent_flow), "Tester process missing"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_"), f"Expected Tester output, got {result.code}"

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
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
        logger.debug(f"Agent flow after agent creation: {agent_flow}")
        assert len(agent_flow) >= 2, f"Expected at least 2 init entries, got {len(agent_flow)}: {agent_flow}"

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["output"].startswith("remote_") for a in agent_flow), "Generator process missing"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("remote_generated_from_"), f"Expected remote Generator output, got {result.code}"

def test_aggregate_four_agents():
    """Test 1 aggregate with 4 agents."""
    agent_flow.clear()
    session_id = "test_aggregate_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create aggregate
    aggregate = AggregateForTest(session_id, model_manager)

    # Create task
    task = TaskFactory.create_code_task(
        description="Test message passing with 4 agents.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=False
    )

    # Patch and instantiate agents
    logger.debug("Starting test_aggregate_four_agents")
    with patch('seclorum.agents.architect.Architect', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Architect", **kwargs)) as architect_patch, \
         patch('seclorum.agents.generator.Generator', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Generator", **kwargs)) as generator_patch, \
         patch('seclorum.agents.tester.Tester', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Tester", **kwargs)) as tester_patch, \
         patch('seclorum.agents.executor.Executor', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Executor", **kwargs)) as executor_patch:
        logger.debug(f"Patched Architect: {architect_patch}, Generator: {generator_patch}, Tester: {tester_patch}, Executor: {executor_patch}")
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        from seclorum.agents.tester import Tester
        from seclorum.agents.executor import Executor
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        tester = Tester(f"{task.task_id}_test", session_id, model_manager)
        executor = Executor(f"{task.task_id}_exec", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}, Tester={tester.name}, Executor={executor.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
        aggregate.add_agent(tester, [(generator.name, {"status": "completed"})])
        aggregate.add_agent(executor, [(tester.name, {"status": "completed"})])
        logger.debug(f"Agent flow after agent creation: {agent_flow}")
        assert len(agent_flow) >= 4, f"Expected at least 4 init entries, got {len(agent_flow)}: {agent_flow}"

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 8, f"Expected at least 8 entries (4 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), "Tester init missing"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "instantiated" for a in agent_flow), "Executor init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect process missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), "Generator process missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" for a in agent_flow), "Tester process missing"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "completed" for a in agent_flow), "Executor process missing"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_"), f"Expected Executor output, got {result.code}"

def test_aggregate_complex_pipelines():
    """Test 1 aggregate with complex Architect output feeding multiple pipelines."""
    agent_flow.clear()
    session_id = "test_aggregate_session"
    model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

    # Create aggregate
    aggregate = AggregateForTest(session_id, model_manager)

    # Create task
    task = TaskFactory.create_code_task(
        description="Test complex Architect output with multiple pipelines.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=False
    )

    # Patch and instantiate agents
    logger.debug("Starting test_aggregate_complex_pipelines")
    with patch('seclorum.agents.architect.Architect', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Architect", **kwargs)) as architect_patch, \
         patch('seclorum.agents.generator.Generator', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Generator", **kwargs)) as generator_patch, \
         patch('seclorum.agents.tester.Tester', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Tester", **kwargs)) as tester_patch, \
         patch('seclorum.agents.debugger.Debugger', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Debugger", **kwargs)) as debugger_patch, \
         patch('seclorum.agents.executor.Executor', new=lambda *args, **kwargs: MockAgent(*args, agent_type="Executor", **kwargs)) as executor_patch:
        logger.debug(f"Patched Architect: {architect_patch}, Generator: {generator_patch}, Tester: {tester_patch}, Debugger: {debugger_patch}, Executor: {executor_patch}")
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        from seclorum.agents.tester import Tester
        from seclorum.agents.debugger import Debugger
        from seclorum.agents.executor import Executor
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)
        tester = Tester(f"{task.task_id}_test", session_id, model_manager)
        debugger = Debugger(f"{task.task_id}_debug", session_id, model_manager)
        executor = Executor(f"{task.task_id}_exec", session_id, model_manager)
        logger.debug(f"Created agents: Architect={architect.name}, Generator={generator.name}, Tester={tester.name}, Debugger={debugger.name}, Executor={executor.name}")

        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "completed"})])
        aggregate.add_agent(tester, [(generator.name, {"status": "completed"})])
        aggregate.add_agent(debugger, [(architect.name, {"status": "completed"})])
        aggregate.add_agent(executor, [(debugger.name, {"status": "completed"})])
        logger.debug(f"Agent flow after agent creation: {agent_flow}")
        assert len(agent_flow) >= 5, f"Expected at least 5 init entries, got {len(agent_flow)}: {agent_flow}"

        logger.debug("Starting AggregateForTest.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}")

    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 10, f"Expected at least 10 entries (5 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), "Architect init missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), "Generator init missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), "Tester init missing"
    assert any(a["agent_name"].startswith("Debugger_") and a["status"] == "instantiated" for a in agent_flow), "Debugger init missing"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "instantiated" for a in agent_flow), "Executor init missing"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), "Architect complex output missing"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["output"].startswith("generated_from_design_by_") for a in agent_flow), "Generator process missing"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" and a["output"].startswith("processed_generated_from_") for a in agent_flow), "Tester process missing"
    assert any(a["agent_name"].startswith("Debugger_") and a["status"] == "completed" and a["output"].startswith("debugged_from_spec_by_") for a in agent_flow), "Debugger process missing"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "completed" and a["output"].startswith("processed_debugged_from_") for a in agent_flow), "Executor process missing"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_debugged_from_"), f"Expected Executor output, got {result.code}"

def test_real_agents_message_passing(model_manager):
    """Test 1 aggregate with real Architect and Generator using mocked remote inference."""
    session_id = "test_real_agents_session"
    logger.debug("Starting test_real_agents_message_passing")

    # Create task
    task = TaskFactory.create_code_task(
        description="Generate a 3D drone game design and code.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=True
    )

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
            logger.debug(f"Mocking response for prompt: {prompt[:50]}...")
            if "design" in prompt.lower() or "architect" in prompt.lower():
                logger.debug("Returning Architect response")
                mock.json.return_value = mock_response_architect
            else:
                logger.debug("Returning Generator response")
                mock.json.return_value = mock_response_generator
            mock.status_code = 200
            return mock

        mock_post.side_effect = side_effect

        # Create aggregate
        aggregate = Aggregate(session_id, model_manager)

        # Instantiate real agents
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)

        logger.debug(f"Created real agents: Architect={architect.name}, Generator={generator.name}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "planned"})])
        logger.debug(f"Task parameters before processing: {task.parameters}")

        logger.debug("Starting Aggregate.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}, result_code={result.code[:50] if result else None}")
        logger.debug(f"Task parameters after processing: {task.parameters}")

    # Assertions
    assert architect.name in task.parameters, f"Architect output missing: {task.parameters}"
    assert generator.name in task.parameters, f"Generator output missing: {task.parameters}"
    assert status == "generated", f"Expected status 'generated', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert "scene = new THREE.Scene()" in result.code, "Expected Generator to produce Three.js code"
    architect_output = task.parameters.get(architect.name, {}).get("result")
    assert isinstance(architect_output, CodeOutput), "Architect result should be CodeOutput"
    assert json.loads(architect_output.code).get("design") == "drone_game_design", "Architect design incorrect"
    assert mock_post.called, "Remote inference was not called"
    assert len(mock_post.call_args_list) >= 2, f"Expected at least 2 remote calls, got {len(mock_post.call_args_list)}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
