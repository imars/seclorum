# seclorum/agents/executor.py
import subprocess
import os
from typing import Tuple
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, TestResult
from seclorum.agents.memory_manager import MemoryManager
from seclorum.languages import LANGUAGE_CONFIG

class Executor(Agent):
    def __init__(self, task_id: str, session_id: str):
        super().__init__(f"Executor_{task_id}", session_id)
        self.task_id = task_id
        self.memory = MemoryManager(session_id)
        self.log_update(f"Executor initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, TestResult]:
        self.log_update(f"Executing for Task {task.task_id}")
        generator_output = task.parameters.get("Generator_dev_task", {}).get("result")
        tester_output = task.parameters.get("Tester_dev_task", {}).get("result")
        language = task.parameters.get("language", "python").lower()
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["python"])

        if not generator_output or not isinstance(generator_output, CodeOutput):
            self.log_update("No valid code from Generator")
            result = TestResult(test_code="", passed=False, output="No code provided")
            self.memory.save(response=result, task_id=task.task_id)
            return "tested", result

        code_output = generator_output
        test_result = tester_output if tester_output and isinstance(tester_output, TestResult) else TestResult(test_code="", passed=False)
        full_code = f"{code_output.code}\n\n{test_result.test_code}" if test_result.test_code else code_output.code

        if not full_code.strip():
            self.log_update("No code to execute")
            result = TestResult(test_code=test_result.test_code, passed=False, output="No code provided")
            self.memory.save(response=result, task_id=task.task_id)
            return "tested", result

        temp_file = f"temp_{self.task_id}{config['file_extension']}"
        self.log_update(f"Writing to {temp_file}")
        with open(temp_file, "w") as f:
            f.write(full_code)

        try:
            if language == "javascript":
                if test_result.test_code:
                    cmd = ["npx", "jest", temp_file, "--silent"]
                else:
                    cmd = ["node", temp_file]
            elif language == "python":
                cmd = ["python", "-B", temp_file]
            else:
                self.log_update(f"Unsupported language: {language}")
                result = TestResult(test_code=test_result.test_code, passed=False, output=f"Language {language} not supported")
                self.memory.save(response=result, task_id=task.task_id)
                return "tested", result

            self.log_update(f"Running command: {' '.join(cmd)}")
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=10)
            passed = True
            self.log_update(f"Execution output: {output}")
        except subprocess.CalledProcessError as e:
            self.log_update(f"Execution failed with error: {e.output}")
            output = e.output
            passed = False
        except subprocess.TimeoutExpired as e:
            self.log_update(f"Execution timed out: {e.output}")
            output = e.output.decode('utf-8') if e.output else "Timeout"
            passed = False
        except Exception as e:
            self.log_update(f"Unexpected execution error: {str(e)}")
            output = str(e)
            passed = False
        finally:
            if os.path.exists(temp_file):
                self.log_update(f"Cleaning up {temp_file}")
                os.remove(temp_file)

        result = TestResult(test_code=test_result.test_code, passed=passed, output=output)
        self.log_update(f"Final result: passed={result.passed}, output={result.output}")
        self.memory.save(response=result, task_id=task.task_id)
        self.commit_changes(f"Executed {language} code and tests for Task {task.task_id}")
        return "tested", result

    def start(self):
        self.log_update("Starting executor")

    def stop(self):
        self.log_update("Stopping executor")
