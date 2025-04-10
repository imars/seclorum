# seclorum/agents/tester.py
from seclorum.agents.base import Agent
from seclorum.models import Task, TestResult, CodeOutput
from seclorum.agents.memory_manager import MemoryManager
from seclorum.agents.model_manager import ModelManager

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Tester initialized for Task {task_id}")

    def process_task(self, task: Task) -> tuple[str, TestResult]:
        self.log_update(f"Generating tests for Task {task.task_id}")
        generator_output = task.parameters.get("Generator_dev_task")
        if not generator_output or not isinstance(generator_output["result"], CodeOutput):
            self.log_update("No valid Generator output, returning empty test result")
            result = TestResult(test_code="", passed=False, output="No code provided")
            self.memory.save(response=result, task_id=task.task_id)
            return "tested", result

        code_output = generator_output["result"]
        language = task.parameters.get("language", "python").lower()  # Default to Python

        if code_output.tests:
            test_code = code_output.tests
            self.log_update(f"Using provided {language} test code:\n{test_code}")
        else:
            if language == "javascript":
                test_prompt = (
                    f"Generate a JavaScript unit test (using Jest syntax) for this code:\n{code_output.code}\n"
                    "Return only the raw, executable JavaScript test code without Markdown, comments, or explanations."
                )
            else:  # Python
                test_prompt = (
                    f"Generate a Python unit test for this code:\n{code_output.code}\n"
                    "Return only the raw, executable Python test code without Markdown, comments, or explanations."
                )
            test_code = self.model.generate(test_prompt).strip()
            self.log_update(f"Generated new {language} test code:\n{test_code}")

        # Clean up test code
        test_code = test_code.replace("```javascript", "").replace("```python", "").replace("```", "").strip()

        # Make test self-executing (language-specific)
        if language == "javascript":
            # For Jest, wrap in an IIFE to make it executable standalone
            full_test_code = f"(() => {{\n{test_code}\n}})();"
        else:  # Python
            if "def test_" in test_code:
                test_function_name = test_code.split('def ')[1].split('(')[0]
                full_test_code = f"{test_code}\n\n{test_function_name}()"
            else:
                full_test_code = test_code  # If no function, assume it’s executable

        self.log_update(f"Full executable {language} test code:\n{full_test_code}")

        result = TestResult(test_code=full_test_code, passed=False)  # Executor will determine pass/fail
        self.memory.save(response=result, task_id=task.task_id)
        self.commit_changes(f"Generated {language} tests for {task.task_id}")
        return "tested", result
