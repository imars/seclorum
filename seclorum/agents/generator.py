# seclorum/agents/generator.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_CONFIG
from typing import Tuple

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Generator initialized for Task {task_id} with model {self.model_manager.model_name}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        self.log_update(f"Generating code for task: {task.description}")
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        code_prompt = config["code_prompt"].format(description=task.description) + (
            " Return only the raw, executable code suitable for runtime environments, "
            "without tags, markup, comments, or explanations."
            if language == "javascript" else ""
        )
        use_remote = task.parameters.get("use_remote", None)
        code = self.infer(code_prompt, use_remote=use_remote)
        self.log_update(f"Raw generated code:\n{code}")

        tests = None
        if task.parameters.get("generate_tests", False) and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code)
            tests = self.infer(test_prompt, use_remote=use_remote)
            self.log_update(f"Generated tests:\n{tests}")

        result = CodeOutput(code=code, tests=tests)
        self.store_output(task, "generated", result)  # Use generic storage
        self.commit_changes(f"Generated {language} code for task")
        return "generated", result

        tests = None
        if task.parameters.get("generate_tests", False) and config["test_prompt"]:
            test_prompt = config["test_prompt"].format(code=code) + (
                " Return only the raw Jest test code for Node.js, without Markdown or comments."
                if language == "javascript" else ""
            )
            tests = self.infer(test_prompt, use_remote=use_remote)
            self.log_update(f"Generated tests:\n{tests}")

        result = CodeOutput(code=code, tests=tests)
        self.store_output(task, "generated", result)  # Uses "Generator_dev_task"
        self.log_update(f"CodeOutput created: {result}")
        self.memory.save(response=result, task_id=task.task_id)
        task.parameters["Generator_dev_task"] = {"status": "generated", "result": result}
        self.commit_changes(f"Generated {language} code and tests for {task.task_id}")
        return "generated", result

    def start(self):
        self.log_update("Starting generator")

    def stop(self):
        self.log_update("Stopping generator")
