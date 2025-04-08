# tests/test_developer.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid tokenizer parallelism warnings
import logging
import unittest
from io import StringIO
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
        print(f"Success raw history: {history}")
        print(f"Success formatted history:\n{developer.memory.format_history(task_id=task.task_id)}")

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
                    return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[999]"
                elif "Generate a Python unit test" in prompt:
                    return "import os\ndef test_buggy_list_files():\n    result = buggy_list_files()\n    assert isinstance(result, str)"
                elif "Fix this Python code" in prompt:
                    return "import os\ndef buggy_list_files():\n    files = os.listdir('.')\n    return files[0] if files else ''"
                return "Mock debug response"

        model_manager = DebugMockModelManager()
        developer = Developer(session_id, model_manager)
        developer.start()

        status, result = developer.orchestrate(task)

        print(f"Debug status: {status}")
        print(f"Debug result: {result}")
        history = developer.memory.load_history(task_id=task.task_id)
        print(f"Debug raw history: {history}")
        print(f"Debug formatted history:\n{developer.memory.format_history(task_id=task.task_id)}")
        debug_entries = [entry for entry in history if "Fixed code" in (entry["response"] or "")]
        print(f"Debug entries: {debug_entries}")

        self.assertEqual(status, "debugged", f"Expected 'debugged', got {status}")
        self.assertIsInstance(result, CodeOutput, "Result should be CodeOutput after debugging")
        self.assertTrue("files[0]" in result.code or "''" in result.code, "Debugged code should fix IndexError")
        self.assertTrue(len(debug_entries) > 0, "Debugging step should be in history")

        developer.stop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Developer agent tests")
    parser.add_argument("--quiet", action="store_true", help="Suppress detailed output")
    args = parser.parse_args()

    setup_logging(args.quiet)

    # Capture output to a file
    output_file = "test_developer_output.txt"
    original_stdout = sys.stdout  # Save original stdout
    with open(output_file, "w") as f:
        # Use StringIO to capture output, then write to both file and console
        buffer = StringIO()
        sys.stdout = buffer

        # Run tests
        runner = unittest.TextTestRunner(stream=buffer, verbosity=2 if not args.quiet else 0)
        result = unittest.main(testRunner=runner, exit=False, argv=[sys.argv[0]] + (["-q"] if args.quiet else []))

        # Restore stdout and write to file and console
        sys.stdout = original_stdout
        test_output = buffer.getvalue()
        print(test_output)  # Print to console
        f.write(test_output)  # Write to file

    # Indicate where the output was saved
    print(f"Test output saved to {output_file}")
