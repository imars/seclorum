import sys
import time
import subprocess
from .base import Agent

class Worker(Agent):
    def __init__(self, task_id, description, node_name):
        super().__init__(name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.node_name = node_name
        self.model = "deepseek-r1:8b" if description.startswith("[complex]") else "llama3.2"

    def start(self):
        """Start the worker and process the task."""
        self.log_update(f"Worker started for Task {self.task_id}: {self.description} using {self.model}")
        self.process_task()
        self.stop()

    def stop(self):
        """Stop the worker and log completion."""
        self.log_update(f"Worker stopped for Task {self.task_id}")
        print(f"Worker completed Task {self.task_id}")

    def process_task(self):
        """Process the task using Ollama with the selected model."""
        print(f"Processing Task {self.task_id}: {self.description} with {self.model}")
        time.sleep(1)  # Simulate initial setup
        task_input = self.description.replace("[complex]", "").strip()
        
        # Check if Ollama is available
        for attempt in range(3):
            try:
                subprocess.check_call(["ollama", "ps"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"Ollama is running on attempt {attempt + 1}")
                break
            except subprocess.CalledProcessError:
                self.log_update(f"Ollama not responding on attempt {attempt + 1}")
                time.sleep(2)
        else:
            result = "Failed: Ollama server not available after 3 attempts"
            self.log_update(f"Task {self.task_id} result: {result}")
            self.report_result(result)
            return

        # Process with Ollama
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
        self.log_update(f"Task {self.task_id} result: {result}")
        self.report_result(result)

    def report_result(self, result):
        """Send the result back to MasterNode."""
        from seclorum.agents.master import MasterNode
        master = MasterNode()
        master.receive_update(self.node_name, f"Task {self.task_id} completed: {result}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python worker.py <task_id> <description> <node_name>")
        sys.exit(1)
    task_id, description, node_name = sys.argv[1], sys.argv[2], sys.argv[3]
    worker = Worker(task_id, description, node_name)
    worker.start()
