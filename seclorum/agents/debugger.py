# seclorum/agents/debugger_agent.py
import subprocess
import os
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

    def process_task(self, task: Task) -> tuple[str, str | TestResult]:
        self.logger.info(f"Debugging for Task {task.task_id}")
        code_output = CodeOutput(**task.parameters.get("code_output", {}))
        test_result = TestResult(**task.parameters.get("test_result", {"test_code": "", "passed": False}))
        error = task.parameters.get("error", "")

        debug_prompt = f"Fix this Python code that failed with error:\n{error}\n\nCode:\n{code_output.code}"
        fixed_code = self.model.generate(debug_prompt)

        temp_file = f"temp_{task.task_id}.py"
        with open(temp_file, "w") as f:
            full_code = f"{fixed_code}\n\n{test_result.test_code}" if test_result.test_code else fixed_code
            f.write(full_code)

        try:
            output = subprocess.check_output(["python", temp_file], stderr=subprocess.STDOUT, text=True)
            if test_result.test_code:
                result = TestResult(test_code=test_result.test_code, passed=True, output=output)
                status = "debugged_test"
            else:
                result = f"Code debugged and executed:\n{fixed_code}\nOutput:\n{output}\nOriginal error:\n{error}"
                status = "debugged"
        except subprocess.CalledProcessError as e:
            result = f"Debugging failed:\n{fixed_code}\nError:\n{e.output}\nOriginal error:\n{error}"
            status = "failed"
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        self.memory.save(response=f"Task {task.task_id} result: {result.model_dump_json() if isinstance(result, TestResult) else result}", task_id=task.task_id)
        self.logger.info(f"Task {task.task_id} {status}: {result}")
        return status, result

    def start(self):
        self.log_update("Starting debugger")

    def stop(self):
        self.log_update("Stopping debugger")
