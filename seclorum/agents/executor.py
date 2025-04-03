# seclorum/agents/executor.py
import subprocess
import os
from seclorum.agents.base import AbstractAgent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.memory_manager import MemoryManager

class Executor(AbstractAgent):
    def __init__(self, task_id: str, session_id: str, memory: MemoryManager = None):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.memory = memory or MemoryManager(session_id)
        self.log_update(f"Executor initialized for Task {task_id}")

    def process_task(self, task: Task) -> tuple[str, TestResult]:
        self.log_update(f"Executing for Task {task.task_id}")
        code_output = CodeOutput(**task.parameters.get("code_output", {}))
        test_result = TestResult(**task.parameters.get("test_result", {"test_code": "", "passed": False}))
        full_code = f"{code_output.code}\n\n{test_result.test_code}" if test_result.test_code else code_output.code
        self.log_update(f"Executing code:\n{full_code}")

        temp_file = f"temp_{task.task_id}.py"
        with open(temp_file, "w") as f:
            f.write(full_code)

        try:
            output = subprocess.check_output(["python", temp_file], stderr=subprocess.STDOUT, text=True)
            self.log_update(f"Execution output: {output}")
            if test_result.test_code:
                result = TestResult(test_code=test_result.test_code, passed=True, output=output)
                status = "tested"
            else:
                result = TestResult(test_code="", passed=True, output=output)
                status = "executed"
        except subprocess.CalledProcessError as e:
            self.log_update(f"Execution failed with error: {e.output}")
            result = TestResult(test_code=test_result.test_code, passed=False, output=e.output)
            status = "failed" if not test_result.test_code else "tested"
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        self.memory.save(response=f"Task {task.task_id} result: {result.model_dump_json()}", task_id=task.task_id)
        self.commit_changes(f"Executed code and tests for Task {task.task_id}")
        return status, result

    def start(self):
        self.log_update("Starting executor")

    def stop(self):
        self.log_update("Stopping executor")
