# tests/test_developer.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import logging
import unittest
import time
import json
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.agents.developer import Developer

print("Starting test script")  # Initial marker

def setup_logging(quiet: bool = False):
    level = logging.DEBUG if not quiet else logging.WARNING
    logging.basicConfig(level=level, format="[%(levelname)s] %(name)s: %(message)s", force=True)  # Force reset
    for name in ["seclorum", "seclorum.agents.base", "seclorum.agents.executor", "seclorum.agents.debugger"]:
        logging.getLogger(name).setLevel(level)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    print(f"Logging initialized to level: {logging.getLevelName(level)}")

def format_history(history):
    if not history:
        return "No history available"
    formatted = "Recent History:\n"
    for entry in history[-3:]:
        timestamp = entry.get("timestamp", "Unknown")
        response = entry.get("response", "No response")
        try:
            parsed = json.loads(response) if response.startswith("{") else response
            if isinstance(parsed, dict):
                formatted += f"- {timestamp}:\n  {json.dumps(parsed, indent=2)}\n"
            else:
                formatted += f"- {timestamp}:\n  {parsed.strip()}\n"
        except json.JSONDecodeError:
            formatted += f"- {timestamp}:\n  {response.strip()}\n"
    return formatted

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

class TestDeveloper(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session"
        self.task_id = f"test_task_{unittest.TestCase.id(self).split('.')[-1]}"
        self.model_manager = MockModelManager()
        self.task = Task(task_id=self.task_id, description="Generate buggy code", parameters={})

    def test_executor_to_debugger(self):
        print(f"Starting test_executor_to_debugger with task_id: {self.task_id}")
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        print(f"Developer graph: {developer.graph}")  # Dump graph
        status, result = developer.orchestrate(self.task)
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(format_history(history))
        self.assertEqual(status, "debugged")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("buggy_files", result.code)
        debug_entries = [e for e in history if "Fixed code" in str(e["response"])]
        self.assertTrue(len(debug_entries) > 0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Developer agent tests")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    args = parser.parse_args()

    setup_logging(args.quiet)

    output_file = "test_developer_output.txt"
    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=2 if not args.quiet else 0)
    suite = unittest.TestSuite()
    suite.addTest(TestDeveloper('test_executor_to_debugger'))  # Isolate this test
    result = runner.run(suite)
    elapsed_time = time.time() - start_time
    with open(output_file, "w") as f:
        f.write(f"Ran {result.testsRun} tests in {elapsed_time:.3f}s\n")
        if result.wasSuccessful():
            f.write("OK\n")
        else:
            f.write(f"FAILED (failures={len(result.failures)}, errors={len(result.errors)})\n")
            for fail in result.failures:
                f.write(f"{fail[0]}\n{fail[1]}\n")
    print(f"Test output saved to {output_file}")
