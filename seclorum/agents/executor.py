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

        # Extract code and test from previous agents
        code_output = task.parameters.get("result") if isinstance(task.parameters.get("result"), CodeOutput) else CodeOutput(code="")
        test_result = task.parameters.get("result") if isinstance(task.parameters.get("result"), TestResult) else TestResult(test_code="", passed=False)

        # Combine code and test, ensuring test calls the function
        full_code = f"{code_output.code}\n\n{test_result.test_code}" if test_result.test_code else code_output.code
        self.log_update(f"Executing code:\n{full_code}")

        temp_file = f"temp_{task.task_id}.py"
        self.log_update(f"Writing to {temp_file}")
        with open(temp_file, "w") as f:
            f.write(full_code)

        try:
            cmd = ["python", temp_file]
            self.log_update(f"Running command: {' '.join(cmd)}")
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
            self.log_update(f"Execution output: {output}")
            result = TestResult(test_code=test_result.test_code, passed=True, output=output)
            status = "tested"
        except subprocess.CalledProcessError as e:
            self.log_update(f"Execution failed with error: {e.output}")
            result = TestResult(test_code=test_result.test_code, passed=False, output=e.output)
            status = "tested"
        except Exception as e:
            self.log_update(f"Unexpected execution error: {str(e)}")
            result = TestResult(test_code=test_result.test_code, passed=False, output=str(e))
            status = "tested"
        finally:
            if os.path.exists(temp_file):
                self.log_update(f"Cleaning up {temp_file}")
                os.remove(temp_file)

        self.memory.save(response=result, task_id=task.task_id)
        self.commit_changes(f"Executed code and tests for Task {task.task_id}")
        return status, result

    def start(self):
        self.log_update("Starting executor")

    def stop(self):
        self.log_update("Stopping executor")
