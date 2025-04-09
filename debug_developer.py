# debug_developer.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import logging
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.agents.developer import Developer

# Force logging to stdout
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(name)s: %(message)s", force=True)
for name in ["seclorum", "seclorum.agents.base", "seclorum.agents.executor", "seclorum.agents.debugger"]:
    logging.getLogger(name).setLevel(logging.DEBUG)
print("Logging initialized", file=sys.stdout, flush=True)

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name)
    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef buggy_files():\n    files = os.listdir('.')\n    return files[999]"
        elif "Generate a Python unit test" in prompt:
            return "import os\ndef test_buggy_files():\n    result = buggy_files()\n    assert isinstance(result, str)\n    print('This should not print')\n\ntest_buggy_files()"
        elif "Fix this Python code" in prompt:
            return "import os\ndef buggy_files():\n    return os.listdir('.')[0] if os.listdir('.') else ''"
        return "Mock debug response"

# Simple test
session_id = "test_session"
task_id = "debug_task"
model_manager = MockModelManager()
task = Task(task_id=task_id, description="Generate buggy code", parameters={})

print(f"Starting debug with task_id: {task_id}", file=sys.stdout, flush=True)
developer = Developer(session_id, model_manager)
developer.start()
print(f"Developer graph: {developer.graph}", file=sys.stdout, flush=True)

status, result = developer.orchestrate(task)
print(f"Status: {status}, Result: {result}", file=sys.stdout, flush=True)

history = developer.memory.load_history(task_id)
for entry in history[-3:]:
    print(f"History entry: {entry}", file=sys.stdout, flush=True)

if status != "debugged":
    print("Debug failed!", file=sys.stdout, flush=True)
else:
    print("Debug succeeded!", file=sys.stdout, flush=True)
