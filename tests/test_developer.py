# tests/test_developer.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import logging
import unittest
from io import StringIO
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.agents.developer import Developer
from typing import Any, Dict, List, Optional, Tuple

def setup_logging(quiet: bool = False):
    level = logging.WARNING if quiet else logging.INFO
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers[:]:
        handler.setLevel(level)
    for logger_name in logging.Logger.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(level)

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name)
    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef list_files():\n    return os.listdir('.')"
        elif "Generate a Python unit test" in prompt:
            return "import os\ndef test_list_files():\n    result = list_files()\n    assert isinstance(result, list)"
        elif "Fix this Python code" in prompt:
            return "import os\ndef list_files():\n    return os.listdir('.') if os.listdir('.') else []"
        return "Mock response"

class TestDeveloper(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session"
        self.task_id = "test_task_1"
        self.model_manager = MockModelManager()
        self.task = Task(task_id=self.task_id, description="List files", parameters={})

    def test_architect_to_generator(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Generator_dev_task")
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
        self.assertEqual(status, "generated")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("list_files", result.code)

    def test_generator_to_tester(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Tester_dev_task")
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertIn("test_list_files", result.test_code)

    def test_tester_to_executor(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Executor_dev_task")
        history = developer.memory.load_history(self.task_id)
        executor_logs = [log for log in developer.get_logs() if "Executor" in log["message"]]
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
        print(f" {executor_logs}")
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertTrue(result.passed, f"Execution failed: {result.output}")

    def test_executor_to_debugger(self):
        self.task.description = "Generate buggy code"
        self.model_manager.generate = lambda prompt, **kwargs: (
            "import os\ndef buggy_files():\n    return os.listdir('.')[999]"
            if "Generate Python code" in prompt else
            "import os\ndef test_buggy_files():\n    result = buggy_files()\n    assert isinstance(result, str)"
            if "Generate a Python unit test" in prompt else
            "import os\ndef buggy_files():\n    return os.listdir('.')[0] if os.listdir('.') else ''"
            if "Fix this Python code" in prompt else
            "Mock debug response"
        )
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task)  # No stop_at for full flow
        history = developer.memory.load_history(self.task_id)
        executor_logs = [log for log in developer.get_logs() if "Executor" in log["message"]]
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
        print(f"Executor logs: {executor_logs}")
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
    original_stdout = sys.stdout
    with open(output_file, "w") as f:
        buffer = StringIO()
        sys.stdout = buffer
        runner = unittest.TextTestRunner(stream=buffer, verbosity=2 if not args.quiet else 0)
        unittest.main(testRunner=runner, exit=False, argv=[sys.argv[0]] + (["-q"] if args.quiet else []))
        sys.stdout = original_stdout
        test_output = buffer.getvalue()
        print(test_output)
        f.write(test_output)
    print(f"Test output saved to {output_file}")
