# seclorum/agents/debugger.py
from seclorum.agents.agent import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from typing import Tuple
import logging

class Debugger(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Debugger_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Debugger initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        self.log_update(f"Debugging code for task: {task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")

        executor_key = next((k for k in task.parameters if k.startswith("Executor_") and k.endswith("_exec")), None)
        code_output = None
        if executor_key and executor_key in task.parameters:
            code_output = task.parameters.get(executor_key, {}).get("result")

        if not code_output or not code_output.test_code:
            self.log_update(f"No execution results to debug for {output_file}")
            return "debugged", CodeOutput(code="", tests=None)

        prompt = (
            f"Debug the following code based on execution results:\n{code_output.output}\n\n"
            f"Provide fixed code for {output_file} in {language}. Return only the corrected code."
        )
        use_remote = task.parameters.get("use_remote", False)
        fixed_code = self.infer(prompt, task, use_remote=use_remote, use_context=False)
        self.log_update(f"Fixed code for {output_file}: {fixed_code[:100]}...")

        result = CodeOutput(code=fixed_code, tests=None)
        self.save_output(task, result, status="debugged")
        self.commit_changes(f"Debugged {language} code for {output_file}")
        return "debugged", result

    def start(self):
        self.log_update("Starting debugger")

    def stop(self):
        self.log_update("Stopping debugger")
