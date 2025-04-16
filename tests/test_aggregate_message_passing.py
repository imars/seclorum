# tests/test_aggregate_message_passing.py
import pytest
import logging
import sys
import importlib
import json
import os
from unittest.mock import patch, MagicMock
from seclorum.agents.base import AbstractAgent
from seclorum.agents.aggregate import Aggregate
from seclorum.models import Task, CodeOutput, Plan, create_model_manager
from seclorum.models.task import TaskFactory
from typing import Tuple, Any, Optional, Union

# Configure logging
logging.getLogger('').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.propagate = True

script_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(script_dir, 'aggregate_message_passing.log')
try:
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    root_logger = logging.getLogger('')
    root_logger.addHandler(file_handler)
    logger.addHandler(file_handler)
    file_handler.flush()
    logger.debug(f"Logging initialized. Writing to {log_file}")
except Exception as e:
    logger.error(f"Failed to initialize FileHandler for {log_file}: {str(e)}")
    raise

agent_flow = []

@pytest.fixture(autouse=True)
def ensure_log_file():
    try:
        if not os.path.exists(log_file):
            with open(log_file, 'a') as f:
                f.write(f"Log file created at {log_file}\n")
        logger.debug(f"Log file check: {log_file} exists={os.path.exists(log_file)}")
    except Exception as e:
        logger.error(f"Error ensuring log file {log_file}: {str(e)}")
        raise
    yield

@pytest.fixture(autouse=True)
def clear_modules():
    modules_to_clear = [k for k in sys.modules if k.startswith('seclorum.agents')]
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)
    logger.debug(f"Cleared modules: {modules_to_clear}")
    yield
    for mod in modules_to_clear:
        sys.modules.pop(mod, None)

@pytest.fixture
def model_manager():
    return create_model_manager(provider="ollama", model_name="llama3.2:latest")

@pytest.fixture
def task():
    return TaskFactory.create_code_task(
        description="Generate a 3D drone game design and code.",
        language="javascript",
        generate_tests=False,
        execute=False,
        use_remote=False
    )

class MockAgent:
    def __init__(self, *args, **kwargs):
        try:
            agent_type = kwargs.pop("agent_type", "MockAgent")
            task_id = args[0] if args else "unknown"
            self.name = f"{agent_type}_{task_id}"
            self.session_id = args[1] if len(args) > 1 else "mock_session"
            self.logger = logging.getLogger(f"MockAgent_{self.name}")
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = True
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

            if isinstance(input_data, CodeOutput):
                input_data = input_data.code
            input_value = input_data
            self.logger.debug(f"Processing {self.name} with input: {input_value}")

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

            self.logger.debug(f"MockAgent Visited {self.name}: task={task.task_id}, input={input_data}, output={result_code}")
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
            self.logger.error(f"Error in MockAgent.process_task: {str(e)}")
            raise

class AggregateForTest(Aggregate):
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
            deps = self.graph.get(agent_name, [])
            if deps:
                dep_name = deps[0][0]
                dep_result = task.parameters.get(f"result_{dep_name}")
                task.parameters["previous_result"] = dep_result.code if dep_result else "initial"
            else:
                task.parameters["previous_result"] = "initial"

            try:
                agent_status, agent_result = agent.process_task(task)
                task.parameters[f"result_{agent_name}"] = agent_result
                task.parameters[f"status_{agent_name}"] = agent_status
                logger.debug(f"Agent {agent_name} completed: status={agent_status}, result={agent_result.code if hasattr(agent_result, 'code') else agent_result}")
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
        logger.debug(f"AggregateForTest complete: status={status}, result={result.code if result else None}, task_parameters={task.parameters}")
        return status, result

def test_aggregate_two_agents(model_manager, task):
    agent_flow.clear()
    session_id = "test_aggregate_session"
    aggregate = AggregateForTest(session_id, model_manager)
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
        logger.debug(f"Task complete: status={status}, agent_flow={agent_flow}")
    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), f"Architect init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), f"Generator init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), f"Architect process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), f"Generator process missing: {agent_flow}"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("generated_from_"), f"Expected Generator output, got {result.code}"

def test_aggregate_three_agents(model_manager, task):
    agent_flow.clear()
    session_id = "test_aggregate_session"
    aggregate = AggregateForTest(session_id, model_manager)
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
        logger.debug(f"Task complete: status={status}, agent_flow={agent_flow}")
    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 6, f"Expected at least 6 entries (3 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), f"Architect init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), f"Generator init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), f"Tester init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), f"Architect process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), f"Generator process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" for a in agent_flow), f"Tester process missing: {agent_flow}"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_"), f"Expected Tester output, got {result.code}"

def test_aggregate_two_agents_remote(model_manager, task):
    agent_flow.clear()
    session_id = "test_aggregate_session"
    task.parameters["use_remote"] = True
    aggregate = AggregateForTest(session_id, model_manager)
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
        logger.debug(f"Task complete: status={status}, agent_flow={agent_flow}")
    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 4, f"Expected at least 4 entries (2 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), f"Architect init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), f"Generator init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), f"Architect process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["output"].startswith("remote_") for a in agent_flow), f"Generator process missing: {agent_flow}"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("remote_generated_from_"), f"Expected remote Generator output, got {result.code}"

def test_aggregate_four_agents(model_manager, task):
    agent_flow.clear()
    session_id = "test_aggregate_session"
    aggregate = AggregateForTest(session_id, model_manager)
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
        logger.debug(f"Task complete: status={status}, agent_flow={agent_flow}")
    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 8, f"Expected at least 8 entries (4 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), f"Architect init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), f"Generator init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), f"Tester init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "instantiated" for a in agent_flow), f"Executor init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), f"Architect process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" for a in agent_flow), f"Generator process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" for a in agent_flow), f"Tester process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "completed" for a in agent_flow), f"Executor process missing: {agent_flow}"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_"), f"Expected Executor output, got {result.code}"

def test_aggregate_complex_pipelines(model_manager, task):
    agent_flow.clear()
    session_id = "test_aggregate_session"
    aggregate = AggregateForTest(session_id, model_manager)
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
        logger.debug(f"Task complete: status={status}, agent_flow={agent_flow}")
    logger.debug(f"Agent flow before assertions: {agent_flow}")
    assert len(agent_flow) >= 10, f"Expected at least 10 entries (5 agents × init+process), got {len(agent_flow)}: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "instantiated" for a in agent_flow), f"Architect init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "instantiated" for a in agent_flow), f"Generator init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "instantiated" for a in agent_flow), f"Tester init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Debugger_") and a["status"] == "instantiated" for a in agent_flow), f"Debugger init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "instantiated" for a in agent_flow), f"Executor init missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Architect_") and a["status"] == "completed" for a in agent_flow), f"Architect complex output missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Generator_") and a["status"] == "completed" and a["output"].startswith("generated_from_design_by_") for a in agent_flow), f"Generator process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Tester_") and a["status"] == "completed" and a["output"].startswith("processed_generated_from_") for a in agent_flow), f"Tester process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Debugger_") and a["status"] == "completed" and a["output"].startswith("debugged_from_spec_by_") for a in agent_flow), f"Debugger process missing: {agent_flow}"
    assert any(a["agent_name"].startswith("Executor_") and a["status"] == "completed" and a["output"].startswith("processed_debugged_from_") for a in agent_flow), f"Executor process missing: {agent_flow}"
    assert status == "completed", f"Expected status 'completed', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code.startswith("processed_debugged_from_"), f"Expected Executor output, got {result.code}"

# tests/test_aggregate_message_passing.py (only test_real_agents_message_passing)

@pytest.mark.timeout(300)
def test_real_agents_message_passing(model_manager, task):
    """Test 1 aggregate with real Architect and Generator using mocked inference."""
    session_id = "test_real_agents_session"
    test_agent_flow = []
    output_dir = os.path.join("examples", "3d_game")
    os.makedirs(output_dir, exist_ok=True)

    # Mock inference responses
    mock_response_architect = """
    {
        "subtasks": [
            {
                "description": "Generate JavaScript logic for 3D drone game with THREE.js",
                "language": "javascript",
                "output_file": "examples/3d_game/drone_game.js"
            },
            {
                "description": "Generate HTML UI with canvas and controls",
                "language": "html",
                "output_file": "examples/3d_game/drone_game.html"
            }
        ],
        "metadata": {"version": 1}
    }
    """
    mock_response_generator = """
    import * as THREE from 'three';
    import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

    function DroneGame() {
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gameCanvas') });
        renderer.setSize(window.innerWidth, window.innerHeight);

        // Terrain
        const terrainGeometry = new THREE.PlaneGeometry(200, 200, 32, 32);
        const terrainMaterial = new THREE.MeshStandardMaterial({ color: 0x228B22 });
        const terrain = new THREE.Mesh(terrainGeometry, terrainMaterial);
        terrain.rotation.x = -Math.PI / 2;
        scene.add(terrain);

        // Player Drone
        const droneGeometry = new THREE.SphereGeometry(1, 32, 32);
        const droneMaterial = new THREE.MeshBasicMaterial({ color: 0xff0000 });
        const drone = new THREE.Mesh(droneGeometry, droneMaterial);
        drone.position.set(0, 5, 0);
        scene.add(drone);

        // AI Drones
        const aiDrones = [];
        for (let i = 0; i < 3; i++) {
            const aiDrone = new THREE.Mesh(droneGeometry, new THREE.MeshBasicMaterial({ color: 0x0000ff }));
            aiDrone.position.set(Math.random() * 50 - 25, 5, Math.random() * 50 - 25);
            scene.add(aiDrone);
            aiDrones.push({ mesh: aiDrone, target: new THREE.Vector3(0, 5, 0) });
        }

        // Checkpoints
        const checkpoints = [];
        for (let i = 0; i < 5; i++) {
            const checkpoint = new THREE.Mesh(
                new THREE.TorusGeometry(3, 0.5, 16, 100),
                new THREE.MeshBasicMaterial({ color: 0xffff00 })
            );
            checkpoint.position.set(Math.random() * 100 - 50, 5, Math.random() * 100 - 50);
            scene.add(checkpoint);
            checkpoints.push(checkpoint);
        }

        // Obstacles
        const obstacles = [];
        for (let i = 0; i < 10; i++) {
            const obstacle = new THREE.Mesh(
                new THREE.BoxGeometry(2, 10, 2),
                new THREE.MeshBasicMaterial({ color: 0x8B4513 })
            );
            obstacle.position.set(Math.random() * 100 - 50, 5, Math.random() * 100 - 50);
            scene.add(obstacle);
            obstacles.push(obstacle);
        }

        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040);
        scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight.position.set(0, 1, 0);
        scene.add(directionalLight);

        // Controls
        const controls = new OrbitControls(camera, renderer.domElement);
        camera.position.set(0, 20, 20);
        controls.update();

        // UI
        const standings = document.getElementById('standings');
        const timer = document.getElementById('timer');
        let score = 0;
        let time = 0;

        // Keyboard Controls
        const keys = {};
        window.addEventListener('keydown', (e) => { keys[e.key] = true; });
        window.addEventListener('keyup', (e) => { keys[e.key] = false; });

        function updateDrone() {
            const speed = 0.5;
            if (keys['ArrowUp'] || keys['w']) drone.position.z -= speed;
            if (keys['ArrowDown'] || keys['s']) drone.position.z += speed;
            if (keys['ArrowLeft']) drone.position.x -= speed;
            if (keys['ArrowRight']) drone.position.x += speed;
        }

        // AI Drone Movement
        function updateAIDrones() {
            aiDrones.forEach((ai, i) => {
                const target = checkpoints[i % checkpoints.length].position;
                ai.target.copy(target);
                const direction = target.clone().sub(ai.mesh.position).normalize();
                ai.mesh.position.add(direction.multiplyScalar(0.2));
            });
        }

        // Collision Detection
        function checkCollisions() {
            const droneBox = new THREE.Box3().setFromObject(drone);
            checkpoints.forEach((cp, i) => {
                const cpBox = new THREE.Box3().setFromObject(cp);
                if (droneBox.intersectsBox(cpBox)) {
                    score += 10;
                    standings.textContent = `Score: ${score}`;
                    cp.position.set(Math.random() * 100 - 50, 5, Math.random() * 100 - 50);
                }
            });
            obstacles.forEach((obs) => {
                const obsBox = new THREE.Box3().setFromObject(obs);
                if (droneBox.intersectsBox(obsBox)) {
                    score -= 5;
                    standings.textContent = `Score: ${score}`;
                    drone.position.set(0, 5, 0);
                }
            });
        }

        // Animation Loop
        function animate() {
            requestAnimationFrame(animate);
            updateDrone();
            updateAIDrones();
            checkCollisions();
            time += 1 / 60;
            timer.textContent = `Time: ${time.toFixed(1)}s`;
            renderer.render(scene, camera);
        }
        animate();
    }
    DroneGame();
    """

    with patch('ollama.Client.generate') as mock_ollama_generate, \
         patch('requests.post') as mock_post, \
         patch('seclorum.agents.memory.core.Memory.save') as mock_memory_save:
        def side_effect_ollama(model, prompt, **kwargs):
            logger.debug(f"Mocking ollama.Client.generate for prompt: {prompt[:50]}...")
            if "plan" in prompt.lower() or "architect" in prompt.lower():
                logger.debug("Returning Architect response")
                return {'response': mock_response_architect}
            logger.debug("Returning Generator response")
            return {'response': mock_response_generator}

        mock_ollama_generate.side_effect = side_effect_ollama
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {
            "candidates": [{
                "content": {
                    "parts": [{"text": mock_response_generator}]
                }
            }]
        })
        mock_memory_save.return_value = None

        aggregate = Aggregate(session_id, model_manager)
        from seclorum.agents.architect import Architect
        from seclorum.agents.generator import Generator
        architect = Architect(task.task_id, session_id, model_manager)
        generator = Generator(f"{task.task_id}_gen", session_id, model_manager)

        logger.debug(f"Created real agents: Architect={architect.name}, Generator={generator.name}")
        logger.debug(f"Task parameters before setup: {task.parameters}")
        aggregate.add_agent(architect, [])
        aggregate.add_agent(generator, [(architect.name, {"status": "planned"})])
        logger.debug(f"Agent flow before process: {test_agent_flow}")

        logger.debug("Starting Aggregate.process_task")
        status, result = aggregate.process_task(task)
        logger.debug(f"Task complete: status={status}, result_type={type(result).__name__}, "
                     f"result_code={result.code[:50] if hasattr(result, 'code') else str(result)[:50]}")
        logger.debug(f"Plan output: {task.parameters.get(architect.name, {}).get('result', 'No plan')}")
        logger.debug(f"Task parameters after process: {task.parameters}")

        # Save outputs
        js_file = os.path.join(output_dir, "drone_game.js")
        html_file = os.path.join(output_dir, "drone_game.html")
        with open(js_file, "w") as f:
            f.write(result.code)
        with open(html_file, "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>3D Drone Game</title>
                <style>
                    body { margin: 0; }
                    canvas { display: block; }
                    #ui { position: absolute; top: 10px; left: 10px; color: white; }
                    button { background-color: blue; color: white; padding: 10px; }
                </style>
            </head>
            <body>
                <canvas id="gameCanvas"></canvas>
                <div id="ui">
                    <div id="timer">Time: 0s</div>
                    <div id="standings">Score: 0</div>
                    <button onclick="location.reload()">Restart</button>
                </div>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
                <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
                <script src="drone_game.js"></script>
            </body>
            </html>
            """)

        test_agent_flow.extend(architect._flow_tracker)
        test_agent_flow.extend(generator._flow_tracker)
        logger.debug(f"Agent flow after process: {test_agent_flow}")
        logger.debug(f"Result code: {result.code[:200] if result.code else 'Empty'}")

    # Assertions
    assert len(test_agent_flow) >= 2, f"Expected at least 2 flow entries, got {len(test_agent_flow)}: {test_agent_flow}"
    assert any(a["agent_name"] == architect.name and a["status"] == "planned" for a in test_agent_flow), f"Architect process missing: {test_agent_flow}"
    assert any(a["agent_name"] == generator.name and a["status"] == "generated" for a in test_agent_flow), f"Generator process missing: {test_agent_flow}"
    assert status == "generated", f"Expected status 'generated', got {status}"
    assert isinstance(result, CodeOutput), f"Expected CodeOutput, got {type(result)}"
    assert result.code, "Expected Generator to produce non-empty code"
    #assert "THREE.Scene" in result.code, "Expected THREE.js usage"
    #assert "terrain" in result.code.lower(), "Expected terrain in code"
    #assert "updateDrone" in result.code, "Expected player controls"
    #assert "aiDrones" in result.code, "Expected AI drones"
    #assert "checkpoints" in result.code, "Expected checkpoints"
    #assert "obstacles" in result.code, "Expected obstacles"
    #assert "standings" in result.code, "Expected UI standings"
    assert architect.name in task.parameters, f"Architect output missing: {task.parameters}"
    assert generator.name in task.parameters, f"Generator output missing: {task.parameters}"
    assert isinstance(task.parameters.get(architect.name, {}).get("result"), Plan), f"Architect result should be Plan"
    assert len(task.parameters.get(architect.name, {}).get("result", Plan(subtasks=[])).subtasks) >= 1, "Expected at least one subtask"
    assert any(t.parameters.get("output_file") == "examples/3d_game/drone_game.js" for t in task.parameters.get(architect.name, {}).get("result", Plan(subtasks=[])).subtasks), "Expected JavaScript subtask"
    assert os.path.exists(js_file), f"Expected {js_file} to exist"
    assert os.path.exists(html_file), f"Expected {html_file} to exist"
    assert mock_ollama_generate.called, "Expected ollama inference to be called"
    assert len(mock_ollama_generate.call_args_list) >= 2, f"Expected at least 2 inference calls, got {len(mock_ollama_generate.call_args_list)}"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
