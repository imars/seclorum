# seclorum/agents/debugger.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.memory_manager import MemoryManager
from seclorum.agents.model_manager import ModelManager
from seclorum.languages import LANGUAGE_CONFIG

class Debugger(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Debugger_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Debugger initialized for Task {self.task_id}")

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
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        self.log_update(f"Original {language} code:\n{code_output.code}")
        self.log_update(f"Original error: {error}")

        cleaned_code = self._clean_code(code_output.code, config["comment_prefix"])
        cleaned_tests = self._clean_code(code_output.tests, config["comment_prefix"]) if code_output.tests else None

        debug_prompt = config["debug_prompt"].format(error=error, code=cleaned_code)
        fixed_code = self.model.generate(debug_prompt).strip()

        self.log_update(f"Fixed {language} code:\n{fixed_code}")
        result = CodeOutput(code=fixed_code, tests=cleaned_tests)
        self.memory.save(response=f"Fixed code:\n{fixed_code}", task_id=task.task_id)
        self.commit_changes(f"Fixed {language} code for Task {self.task_id}")
        return "debugged", result

    def _clean_code(self, code: str, comment_prefix: str) -> str:
        if not code:
            return ""
        lines = code.split("\n")
        cleaned = []
        in_code_block = False
        for line in lines:
            line = line.strip()
            if line.startswith("```"):
                in_code_block = not in_code_block
                continue
            elif in_code_block or (not line.startswith(comment_prefix) and not line.startswith("Error:")):
                cleaned.append(line)
        return "\n".join(cleaned).strip()
