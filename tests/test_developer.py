# tests/test_developer.py (relevant tests only)
class TestDeveloper(unittest.TestCase):
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
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
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
        status, result = developer.orchestrate(self.task)  # No stop_at to allow full flow
        history = developer.memory.load_history(self.task_id)
        print(f"Status: {status}, Result: {result}")
        print(f"History: {history}")
        self.assertEqual(status, "debugged")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("buggy_files", result.code)
        debug_entries = [e for e in history if "Fixed code" in str(e["response"])]
        self.assertTrue(len(debug_entries) > 0)
