# seclorum/agents/tester.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult, ModelManager
from seclorum.languages import LANGUAGE_CONFIG

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Tester_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.log_update(f"Tester initialized for Task {task.task_id}")

    def process_task(self, task: Task) -> tuple[str, TestResult]:
        self.log_update(f"Testing for Task {task.task_id}")
        generator_output = task.parameters.get("Generator_dev_task", {}).get("result")

        if not generator_output or not isinstance(generator_output, CodeOutput):
            self.log_update("No valid code from Generator")
            return "tested", TestResult(test_code="", passed=False, output="No code provided")

        code_output = generator_output
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        test_code = ""
        if config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code_output.code)
            test_code = self.model.generate(test_prompt).strip()
            test_code = test_code.replace(f"```{language}", "").replace("```", "").strip()

        result = TestResult(test_code=test_code, passed=False)
        self.log_update(f"Generated {language} test code:\n{test_code}")
        return "tested", result
