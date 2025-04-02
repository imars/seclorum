# tests/test_pydantic_agents.py
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
from seclorum.agents.debugger import Debugger
from seclorum.agents.model_manager import ModelManager
from seclorum.agents.memory.core import ConversationMemory  # Updated import

logging.basicConfig(level=logging.DEBUG)

def test_agent_workflow():
    session_id = "test_session"
    task = Task(task_id="test1", description="create a Python script to list all Python files in a directory", parameters={"generate_tests": True})

    master = MasterNode(session_id)
    master.start()

    status, result = master.run(task.task_id, task.description)

    print(f"Final status: {status}")
    print(f"Final result: {result}")
    history = master.memory.load_history(task_id=task.task_id)
    print(f"Raw conversation history: {history}")

    assert status in ["generated", "tested", "debugged"], f"Unexpected status: {status}"
    if status == "tested":
        assert isinstance(result, TestResult), "Result should be TestResult for tested status"
        assert result.passed, "Tests should pass"

    master.stop()

if __name__ == "__main__":
    test_agent_workflow()
    print("Agent workflow tests passed!")
