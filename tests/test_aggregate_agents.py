# tests/test_aggregate_agents.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import argparse
import logging
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from seclorum.models import Task, CodeOutput, TestResult, ModelManager, MockModelManager, create_model_manager
from seclorum.agents.master import MasterNode
from seclorum.agents import Generator, Tester, Executor, Learner

def setup_logging(quiet: bool):
    level = logging.WARNING if quiet else logging.INFO
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers[:]:
        handler.setLevel(level)
    for logger_name in logging.Logger.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(level)

def test_aggregate_workflow():
    session_id = "test_session"
    task = Task(task_id="test1", description="create a Python script to list all Python files in a directory", parameters={"generate_tests": True})
    model_manager = create_model_manager(provider="mock")  # Use factory instead of direct instantiation
    master = MasterNode(session_id, require_redis=False)
    master.graph.clear()
    master.agents.clear()
    generator = Generator("test1", session_id, model_manager)
    tester = Tester("test1", session_id, model_manager)
    executor = Executor("test1", session_id)

    master.add_agent(generator)
    master.add_agent(tester, [(generator.name, {"status": "generated"})])
    master.add_agent(executor, [(tester.name, {"status": "tested"})])

    master.start()
    status, result = master.orchestrate(task)

    print(f"Initial status: {status}")
    print(f"Initial result: {result}")
    history = master.memory.load_history(task_id=task.task_id)
    print(f"Initial history: {history}")

    assert status in ["generated", "tested"], f"Unexpected initial status: {status}"
    if status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult"
        assert result.passed, f"Tests failed: {result.output}"

    learner = Learner("test1", session_id)
    master.add_agent(learner, [(executor.name, {"status": "tested"})])
    status, result = master.orchestrate(task)

    print(f"Final status: {status}")
    print(f"Final result: {result}")
    history = master.memory.load_history(task_id=task.task_id)
    print(f"Final history: {history}")

    assert status in ["tested", "predicted"], f"Unexpected final status: {status}"
    if status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult"
        assert result.passed, f"Tests failed: {result.output}"
    elif status == "predicted":
        assert isinstance(result, str), "Result should be string from Learner"

    master.stop()

def test_aggregate_workflow_with_debugging():
    session_id = "debug_session"
    task = Task(task_id="debug1", description="create a Python script with a bug to debug", parameters={"generate_tests": True})

    class DebugMockModelManager(ModelManager):
        def __init__(self, model_name: str = "debug_mock"):
            super().__init__(model_name)
        def generate(self, prompt: str, **kwargs) -> str:
            if "Generate Python code" in prompt:
                return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[999]"
            elif "Generate a Python unit test" in prompt:
                return "import os\ndef test_buggy_list_files():\n    result = buggy_list_files()\n    assert isinstance(result, str)"
            elif "Fix this Python code" in prompt:
                return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[0] if files else ''"
            return "Mock debug response"

    debug_model_manager = DebugMockModelManager()
    developer = Developer(session_id, debug_model_manager)
    developer.start()

    status, result = developer.orchestrate(task)

    print(f"Debug status: {status}")
    print(f"Debug result: {result}")
    history = developer.memory.load_history(task_id=task.task_id)
    print(f"Debug history: {history}")

    assert status in ["debugged", "tested"], f"Expected 'debugged' or 'tested', got {status}"
    if status == "debugged":
        assert isinstance(result, CodeOutput), "Result should be CodeOutput after debugging"
        assert "files[0]" in result.code or "''" in result.code, "Debugged code should fix IndexError"
    elif status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult"
        assert not result.passed, "Test should fail due to bug"
        assert "IndexError" in (result.output or ""), "Output should indicate IndexError"

    developer.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run aggregate agent workflow tests")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    args = parser.parse_args()

    setup_logging(args.quiet)
    test_aggregate_workflow()
    test_aggregate_workflow_with_debugging()  # Add new test
    if not args.quiet:
        print("Aggregate agent workflow tests passed!")
