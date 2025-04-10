# tests/test_agents.py
import sys
for module in list(sys.modules.keys()):
    if module.startswith("seclorum"):
        sys.modules.pop(module)
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import unittest
from io import StringIO
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.agents.base import Agent
from seclorum.models.manager import create_model_manager
from seclorum.agents.architect import Architect
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.debugger import Debugger

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name)
    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]"  # Updated to match output
        elif "Generate a Python unit test" in prompt:
            return "import os\ndef test_list_files():\n    result = list_files()\n    assert isinstance(result, list)"
        elif "Fix this Python code" in prompt:
            return "import os\ndef list_files():\n    return os.listdir('.') if os.listdir('.') else []"
        return "Mock response"

class TestAgents(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session"
        self.task_id = "test_task_1"
        self.model_manager = MockModelManager()
        self.task = Task(task_id=self.task_id, description="Test task", parameters={})

    def test_architect(self):
        architect = Architect(self.task_id, self.session_id, self.model_manager)
        status, result = architect.process_task(self.task)
        self.assertEqual(status, "planned")
        self.assertIn("Mock response", str(result))

    def test_generator(self):
        generator = Generator(self.task_id, self.session_id, self.model_manager)
        task_with_plan = Task(
            task_id=self.task_id,
            description="Generate code",
            parameters={"Architect_dev_task": {"status": "planned", "result": "Plan"}}
        )
        status, result = generator.process_task(task_with_plan)
        self.assertEqual(status, "generated")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("list_py_files", result.code)  # Updated

    def test_tester(self):
        tester = Tester(self.task_id, self.session_id, self.model_manager)
        code_output = CodeOutput(code="import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]")
        task_with_code = Task(
            task_id=self.task_id,
            description="Test code",
            parameters={"Generator_dev_task": {"status": "generated", "result": code_output}}
        )
        status, result = tester.process_task(task_with_code)
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertIn("test_list_files", result.test_code)

    def test_executor(self):
        executor = Executor(self.task_id, self.session_id)
        test_result = TestResult(
            test_code="import os\ndef test_list_files():\n    result = list_files()\n    assert isinstance(result, list)",
            passed=False
        )
        code_output = CodeOutput(code="import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]")
        task_with_test = Task(
            task_id=self.task_id,
            description="Execute test",
            parameters={"Tester_dev_task": {"status": "tested", "result": test_result},
                        "Generator_dev_task": {"status": "generated", "result": code_output}}
        )
        status, result = executor.process_task(task_with_test)
        self.assertEqual(status, "tested")
        self.assertIsInstance(result, TestResult)
        self.assertTrue(result.passed, f"Executor failed: {result.output}")

    def test_debugger(self):
        debugger = Debugger(self.task_id, self.session_id, self.model_manager)
        test_result = TestResult(
            test_code="import os\ndef test_list_files():\n    result = list_files()\n    assert isinstance(result, list)",
            passed=False,
            output="IndexError"
        )
        code_output = CodeOutput(code="import os\ndef list_py_files():\n    return os.listdir()[999]")
        task_with_failure = Task(
            task_id=self.task_id,
            description="Debug code",
            parameters={"Executor_dev_task": {"status": "tested", "result": test_result},
                        "Generator_dev_task": {"status": "generated", "result": code_output}}
        )
        status, result = debugger.process_task(task_with_failure)
        self.assertEqual(status, "debugged")
        self.assertIsInstance(result, CodeOutput)
        self.assertIn("if os.listdir", result.code)

    def test_agent_model_management(self):
        mock_model = MockModelManager(model_name="mock")
        agent = Agent("TestAgent", "test_session", model_manager=mock_model)

        mock_model_alt = MockModelManager(model_name="mock_alt")
        agent.add_model("mock_alt", mock_model_alt)

        result = agent.infer("Generate Python code to list files")
        self.assertIn("list_py_files", result, "Mock model should generate list_py_files function")

        agent.switch_model("mock_alt")
        self.assertEqual(agent.current_model_key, "mock_alt", "Should switch to mock_alt model")

        agent.switch_model("default")  # Changed from "mock" to "default"
        self.assertEqual(agent.current_model_key, "default", "Should switch back to default model")

if __name__ == "__main__":
    output_file = "test_agents_output.txt"
    original_stdout = sys.stdout
    with open(output_file, "w") as f:
        buffer = StringIO()
        sys.stdout = buffer
        runner = unittest.TextTestRunner(stream=buffer, verbosity=2)
        unittest.main(testRunner=runner, exit=False)
        sys.stdout = original_stdout
        test_output = buffer.getvalue()
        print(test_output)
        f.write(test_output)
    print(f"Test output saved to {output_file}")
