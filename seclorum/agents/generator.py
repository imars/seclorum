# seclorum/agents/generator.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.agents.memory_manager import MemoryManager
from seclorum.languages import LANGUAGE_CONFIG

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager, memory: MemoryManager = None):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.memory = memory or MemoryManager(session_id)
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="codellama")
        self.log_update(f"Generator initialized for Task {task_id} with model {self.model_manager.model_name}")

    def process_task(self, task: Task) -> tuple[str, CodeOutput]:
        self.log_update(f"Generating code for Task {task.task_id}: {task.description}")
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])  # Fallback to Python

        code_prompt = config["code_prompt"].format(description=task.description)
        code = self.model.generate(code_prompt).strip()

        tests = None
        if task.parameters.get("generate_tests", False) and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code)
            tests = self.model.generate(test_prompt).strip()

        # Clean up code
        code = code.replace(f"```{language}", "").replace("```", "").strip()
        if tests:
            tests = tests.replace(f"```{language}", "").replace("```", "").strip()

        result = CodeOutput(code=code, tests=tests)
        self.log_update(f"Generated {language} code:\n{code}")
        if tests:
            self.log_update(f"Generated {language} tests:\n{tests}")
        self.memory.save(response=code, task_id=task.task_id)
        task.parameters["code_output"] = code
        self.commit_changes(f"Generated {language} code and tests for {task.task_id}")
        return "generated", result

    def start(self):
        self.log_update("Starting generator")

    def stop(self):
        self.log_update("Stopping generator")
