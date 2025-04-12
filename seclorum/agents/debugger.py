# seclorum/agents/debugger.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult, create_model_manager, ModelManager
from typing import Tuple, Optional
import re

class Debugger(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Debugger_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Debugger initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        self.log_update(f"Debugging code for task: {task.description}")
        generator_key = f"Generator_{self.task_id}"
        tester_key = f"Tester_{self.task_id}"
        code_output = task.parameters.get(generator_key, {}).get("result")
        test_result = task.parameters.get(tester_key, {}).get("result")

        if not code_output or not code_output.code.strip():
            self.log_update("No valid code to debug")
            return "debugged", CodeOutput(code="", tests=None)

        code = code_output.code
        test_output = test_result.output if test_result and test_result.output else "No test output available"

        debug_prompt = (
            f"Debug the following {task.parameters.get('language', 'javascript')} code:\n"
            f"```javascript\n{code}\n```\n"
            f"Test output:\n{test_output}\n"
            f"Fix any errors and return only the corrected code."
        )
        use_remote = task.parameters.get("use_remote", False)
        fixed_code = self.infer(
            prompt=debug_prompt,
            task=task,
            use_remote=use_remote,
            use_context=False
        )
        fixed_code = re.sub(r'```(?:javascript|python|cpp)?\n|\n```', '', fixed_code).strip()
        self.log_update(f"Fixed code:\n{fixed_code}")

        result = CodeOutput(code=fixed_code, tests=code_output.tests)
        self.save_output(task, result, status="debugged")
        self.commit_changes(f"Debugged {task.parameters.get('language', 'javascript')} code for {task.task_id}")
        return "debugged", result

    def start(self):
        self.log_update("Starting debugger")

    def stop(self):
        self.log_update("Stopping debugger")
