# seclorum/agents/generator.py
from seclorum.agents.base import AbstractAgent
from seclorum.models import Task, CodeOutput
from seclorum.agents.memory_manager import MemoryManager
from seclorum.agents.model_manager import ModelManager

class Generator(AbstractAgent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Generator initialized for Task {task_id}")

    def process_task(self, task: Task) -> tuple[str, CodeOutput]:
        self.log_update(f"Generating code for Task {task.task_id}: {task.description}")
        code_prompt = (
            f"Generate Python code to {task.description}. "
            "Return only the raw, executable Python code without Markdown, comments, or explanations."
        )
        code = self.model.generate(code_prompt).strip()

        test_prompt = (
            f"Generate a Python unit test for this code:\n{code}\n"
            "Return only the raw, executable Python test code without Markdown, comments, or explanations."
        )
        tests = self.model.generate(test_prompt).strip() if task.parameters.get("generate_tests", False) else None

        # Final cleanup (just in case)
        code = code.replace("```python", "").replace("```", "").strip()
        if tests:
            tests = tests.replace("```python", "").replace("```", "").strip()

        result = CodeOutput(code=code, tests=tests)
        self.log_update(f"Generated code:\n{code}")
        if tests:
            self.log_update(f"Generated tests:\n{tests}")
        self.memory.save(response=f"Task {task.task_id} result: {result.model_dump_json()}", task_id=task.task_id)
        self.commit_changes(f"Generated code and tests for {task.task_id}")
        return "generated", result

    def start(self):
        self.log_update("Starting generator")

    def stop(self):
        self.log_update("Stopping generator")
