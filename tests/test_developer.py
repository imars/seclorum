# tests/test_developer.py
"""
Unit tests for the Developer agent in Seclorum.
Ensures the Developer orchestrates its workflow correctly, including debugging failed tests.
"""
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid tokenizer parallelism warnings
import logging
import unittest
from seclorum.models import Task, CodeOutput, TestResult, ModelManager, create_model_manager
from seclorum.agents.developer import Developer

def setup_logging(quiet: bool = False):
    """Configure logging level based on quiet flag."""
    level = logging.WARNING if quiet else logging.INFO
    logging.getLogger().setLevel(level)
    for handler in logging.getLogger().handlers[:]:
        handler.setLevel(level)
    for logger_name in logging.Logger.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(level)

class TestDeveloper(unittest.TestCase):
    def test_developer_workflow_success(self):
        """Test Developer's workflow with a successful code generation and test."""
        session_id = "dev_success_session"
        task = Task(
            task_id="dev_success_1",
            description="create a Python script to list all Python files in a directory",
            parameters={"generate_tests": True}
        )

        class SuccessMockModelManager(ModelManager):
            def __init__(self, model_name: str = "success_mock"):
                super().__init__(model_name)
            def generate(self, prompt: str, **kwargs) -> str:
                if "Generate Python code" in prompt:
                    return "import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]"
                elif "Generate a Python unit test" in prompt:
                    return "import os\ndef test_list_py_files():\n    files = list_py_files()\n    assert isinstance(files, list)"
                return "Mock response"

        model_manager = SuccessMockModelManager()
        developer = Developer(session_id, model_manager)
        developer.start()

        status, result = developer.orchestrate(task)

        print(f"Success status: {status}")
        print(f"Success result: {result}")
        history = developer.memory.load_history(task_id=task.task_id)
        print(f"Success history:\n{history}")

        self.assertEqual(status, "tested", f"Expected 'tested' status, got {status}")
        self.assertIsInstance(result, TestResult, "Result should be TestResult")
        self.assertTrue(result.passed, f"Tests failed: {result.output}")
        self.assertIn("list_py_files", result.test_code, "Test code should reference the generated function")

        developer.stop()

    def test_developer_workflow_with_debugging(self):
        """Test Developer's workflow with a buggy script that requires debugging."""
        session_id = "dev_debug_session"
        task = Task(
            task_id="dev_debug_1",
            description="create a Python script with a bug to debug",
            parameters={"generate_tests": True}
        )

        class DebugMockModelManager(ModelManager):
            def __init__(self, model_name: str = "debug_mock"):
                super().__init__(model_name)
            def generate(self, prompt: str, **kwargs) -> str:
                if "Generate Python code" in prompt:
                    return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[999]"  # Intentional IndexError
                elif "Generate a Python unit test" in prompt:
                    return "import os\ndef test_buggy_list_files():\n    result = buggy_list_files()\n    assert isinstance(result, str)"
                elif "Fix this Python code" in prompt:
                    return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[0] if files else ''"  # Fixed version
                return "Mock debug response"

        model_manager = DebugMockModelManager()
        developer = Developer(session_id, model_manager)
        developer.start()

        status, result = developer.orchestrate(task)

        print(f"Debug status: {status}")
        print(f"Debug result: {result}")
        history = developer.memory.load_history(task_id=task.task_id)
        print(f"Debug history:\n{history}")

        # After debugging, we expect either the fixed code or the failed test result
        self.assertIn(status, ["debugged", "tested"], f"Expected 'debugged' or 'tested', got {status}")
        if status == "debugged":
            self.assertIsInstance(result, CodeOutput, "Result should be CodeOutput after debugging")
            self.assertTrue("files[0]" in result.code or "''" in result.code, "Debugged code should fix IndexError")
        elif status == "tested":
            self.assertIsInstance(result, TestResult, "Result should be TestResult")
            self.assertFalse(result.passed, "Test should fail due to bug")
            self.assertIn("IndexError", result.output or "", "Output should indicate IndexError")

        developer.stop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Developer agent tests")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    args = parser.parse_args()

    setup_logging(args.quiet)
    unittest.main(argv=[sys.argv[0]] + (["-q"] if args.quiet else []), verbosity=2 if not args.quiet else 0)
