# tests/test_aggregate_agents.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)

import logging
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.master import MasterNode
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.learner import Learner
from seclorum.agents.model_manager import ModelManager

logging.basicConfig(level=logging.DEBUG)

def test_aggregate_workflow():
    session_id = "test_session"
    task = Task(task_id="test1", description="create a Python script to list all Python files in a directory", parameters={"generate_tests": True})
    model_manager = ModelManager()

    # Initialize MasterNode with basic graph, no Redis requirement
    master = MasterNode(session_id, require_redis=False)  # Added require_redis=False
    generator = Generator("test1", session_id, model_manager)
    tester = Tester("test1", session_id, model_manager)
    executor = Executor("test1", session_id)

    master.add_agent(generator)
    master.add_agent(tester, [(generator.name, {"status": "generated"})])
    master.add_agent(executor, [(tester.name, {"status": "tested"})])

    # Start and run the workflow
    master.start()
    status, result = master.orchestrate(task)

    print(f"Initial status: {status}")
    print(f"Initial result: {result}")
    history = master.memory.load_history(task_id=task.task_id)
    print(f"Initial history: {history}")

    # Verify initial run
    assert status in ["generated", "tested"], f"Unexpected initial status: {status}"
    if status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult"
        assert result.passed, f"Tests failed: {result.output}"

    # Dynamically add Learner
    learner = Learner("test1", session_id)
    master.add_agent(learner, [(executor.name, {"status": "tested"})])
    status, result = master.orchestrate(task)  # Re-run with Learner

    print(f"Final status: {status}")
    print(f"Final result: {result}")
    history = master.memory.load_history(task_id=task.task_id)
    print(f"Final history: {history}")

    # Verify with Learner
    assert status in ["tested", "predicted"], f"Unexpected final status: {status}"
    if status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult"
        assert result.passed, f"Tests failed: {result.output}"
    elif status == "predicted":
        assert isinstance(result, str), "Result should be string from Learner"
        assert "Predicted response" in result, "Learner didn’t process correctly"

    master.stop()

if __name__ == "__main__":
    test_aggregate_workflow()
    print("Aggregate agent workflow tests passed!")
