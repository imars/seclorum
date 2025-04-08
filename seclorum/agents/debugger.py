# seclorum/agents/debugger.py
from seclorum.agents.base import AbstractAgent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.memory_manager import MemoryManager
from seclorum.agents.model_manager import ModelManager

class Debugger(AbstractAgent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Debugger_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Debugger initialized for Task {task_id}")

    def process_task(self, task: Task) -> tuple[str, CodeOutput]:
        self.log_update(f"Debugging for Task {task.task_id}")
        generator_output = task.parameters.get("Generator_dev_task", {}).get("result")
        executor_output = task.parameters.get("Executor_dev_task", {}).get("result")

        if not isinstance(generator_output, CodeOutput) or not isinstance(executor_output, TestResult):
            self.log_update("Missing code or test result")
            return "debugged", CodeOutput(code="", tests=None)

        code_output = generator_output
        test_result = executor_output
        error = test_result.output or "Unknown error"

        self.log_update(f"Original code:\n{code_output.code}")
        self.log_update(f"Original error: {error}")

        cleaned_code = self._clean_code(code_output.code)
        cleaned_tests = self._clean_code(code_output.tests) if code_output.tests else None

        debug_prompt = (
            f"Fix this Python code that failed with error:\n{error}\n"
            f"Original code:\n{cleaned_code}\n"
            f"Return only the corrected Python code without Markdown or explanations."
        )
        fixed_code = self.model.generate(debug_prompt).strip()

        self.log_update(f"Fixed code:\n{fixed_code}")
        result = CodeOutput(code=fixed_code, tests=cleaned_tests)
        self.memory.save(response=f"Fixed code:\n{fixed_code}", task_id=task.task_id)
        self.commit_changes(f"Fixed code for Task {task.task_id}")
        return "debugged", result

    def _clean_code(self, code: str) -> str:
        if not code:
            return ""
        lines = code.split("\n")
        cleaned = []
        in_code_block = False
        for line in lines:
            line = line.strip()
            if line.startswith("```python"):
                in_code_block = True
                continue
            elif line.startswith("```") and in_code_block:
                in_code_block = False
                continue
            elif in_code_block or (not line.startswith("#") and not line.startswith("Error:")):
                cleaned.append(line)
        return "\n".join(cleaned).strip()
