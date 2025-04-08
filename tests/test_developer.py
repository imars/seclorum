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
import json
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.agents.developer import Developer

def setup_logging(quiet: bool = False):
    level = logging.WARNING if quiet else logging.INFO
    logging.getLogger("seclorum").setLevel(level)
    for handler in logging.getLogger().handlers[:]:
        handler.setLevel(level)
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("seclorum"):
            logging.getLogger(logger_name).setLevel(level)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)

def format_history(history):
    """Format history entries for readable output."""
    if not history:
        return "No history available"
    formatted = "Recent History:\n"
    for entry in history[-3:]:  # Last 3 entries
        timestamp = entry.get("timestamp", "Unknown")
        response = entry.get("response", "No response")
        try:
            # Try to parse as JSON for TestResult/CodeOutput
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
            return "import os\ndef list_files():\n    return os.listdir('.')"
        elif "Generate a Python unit test" in prompt:
            return "import os\ndef test_list_files():\n    result = list_files()\n    assert isinstance(result, list)"
        elif "Fix this Python code" in prompt:
            return "import os\ndef list_files():\n    return os.listdir('.') if os.listdir('.') else ''"
        return "Mock response"

class TestDeveloper(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session"
        # Unique task_id per test to avoid history overlap
        self.task_id = f"test_task_{unittest.TestCase.id(self).split('.')[-1]}"
        self.model_manager = MockModelManager()
        self.task = Task(task_id=self.task_id, description="List files", parameters={})

    def test_architect_to_generator(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Generator_dev_task")
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(format_history(history))
        self.assertEqual(status, "generated")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("list_files", result.code)

    def test_generator_to_tester(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Tester_dev_task")
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(format_history(history))
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertIn("test_list_files", result.test_code)

    def test_tester_to_executor(self):
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
        status, result = developer.orchestrate(self.task, stop_at="Executor_dev_task")
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(format_history(history))
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertTrue(result.passed, f"Execution failed: {result.output}")

    def test_executor_to_debugger(self):
        self.task.description = "Generate buggy code"
        self.model_manager.generate = lambda prompt, **kwargs: (
            "import os\ndef buggy_files():\n    files = os.listdir('.')\n    return files[999]"
            if "Generate Python code" in prompt else
            "import os\ndef test_buggy_files():\n    result = buggy_files()\n    assert isinstance(result, str)\n    print('This should not print')"
            if "Generate a Python unit test" in prompt else
            "import os\ndef buggy_files():\n    return os.listdir('.')[0] if os.listdir('.') else ''"
            if "Fix this Python code" in prompt else
            "Mock debug response"
        )
        developer = Developer(self.session_id, self.model_manager)
        developer.start()
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
