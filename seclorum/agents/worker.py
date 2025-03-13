import sys
import time
import subprocess
import os
from .base import Agent

class Worker(Agent):
    def __init__(self, task_id, description, node_name):
        super().__init__(name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.node_name = node_name
        self.model = "deepseek-r1:8b" if description.startswith("[complex]") else "llama3.2:latest"
        print(f"Worker_{task_id}: Initialized with {self.model}")
        self.log_update(f"Worker loaded from: {os.path.abspath(__file__)}")

    def start(self):
        print(f"Worker_{self.task_id}: Starting")
        self.log_update(f"Worker started for Task {self.task_id}: {self.description} using {self.model}")
        self.process_task()
        self.stop()

    def stop(self):
        self.log_update(f"Worker stopped for Task {self.task_id}")
        print(f"Worker completed Task {self.task_id}")

    def process_task(self):
        print(f"Worker_{self.task_id}: Processing task")
        time.sleep(1)
        task_input = self.description.replace("[complex]", "").strip()
        
        for attempt in range(3):
            try:
                subprocess.check_call(["ollama", "ps"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.log_update(f"Ollama is running on attempt {attempt + 1}")
                break
            except subprocess.CalledProcessError as e:
                self.log_update(f"Ollama not responding on attempt {attempt + 1}: {str(e)}")
                time.sleep(2)
        else:
            result = "Failed: Ollama server not available after 3 attempts"
            self.log_update(f"Task {self.task_id} result: {result}")
            self.report_result(result)
            return

        try:
            process = subprocess.Popen(
                ["ollama", "run", self.model, f"Respond to this task: {task_input}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=60)
            if process.returncode == 0:
                result = stdout.strip()
            else:
                result = f"Error processing task with Ollama ({self.model}): {stderr.strip()}"
        except subprocess.TimeoutExpired:
            process.kill()
            result = f"Task timed out after 60s with {self.model}"
        except subprocess.CalledProcessError as e:
            result = f"Error processing task with Ollama ({self.model}): {e.output}"
        except Exception as e:
            result = f"Unexpected error: {str(e)}"
        self.log_update(f"Task {self.task_id} result: {result}")
        self.report_result(result)

    def report_result(self, result):
        try:
            from seclorum.agents.master import MasterNode
            master = MasterNode()
            master.receive_update(self.node_name, f"Task {self.task_id} completed: {result}")
        except Exception as e:
            print(f"Worker_{self.task_id}: Failed to report result: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python worker.py <task_id> <description> <node_name>")
        sys.exit(1)
    task_id, description, node_name = sys.argv[1], sys.argv[2], sys.argv[3]
    worker = Worker(task_id, description, node_name)
    worker.start()
