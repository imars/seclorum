# seclorum/agents/tester.py
from seclorum.agents.base import AbstractAgent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.memory_manager import MemoryManager
from seclorum.models import Task, TestResult, create_model_manager, ModelManager

class Tester(AbstractAgent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Tester initialized for Task {task_id}")

    def process_task(self, task: Task) -> tuple[str, TestResult]:
        self.log_update(f"Generating tests for Task {task.task_id}")
        code_output = CodeOutput(**task.parameters.get("code_output", {}))
    
        if code_output.tests:
            test_code = code_output.tests
            self.log_update(f"Using provided test code:\n{test_code}")
        else:
            test_prompt = (
                f"Generate a Python unit test for this code:\n{code_output.code}\n"
                "Return only the raw, executable Python test code without Markdown, comments, or explanations."
            )
            test_code = self.model.generate(test_prompt).strip()
            self.log_update(f"Generated new test code:\n{test_code}")

        # Clean residual Markdown
        test_code = test_code.replace("```python", "").replace("```", "").strip()

        result = TestResult(test_code=test_code, passed=False)
        self.memory.save(response=result, task_id=task.task_id)  # Pass TestResult object
        task.parameters["result"] = result  # Pass test result downstream
        self.commit_changes(f"Generated tests for {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting tester")

    def stop(self):
        self.log_update("Stopping tester")
