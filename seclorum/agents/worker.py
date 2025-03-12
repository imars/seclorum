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
        # Clean description for complex tasks
        task_input = self.description.replace("[complex]", "").strip()
        try:
            result = subprocess.check_output(
                ["ollama", "run", self.model, f"Respond to this task: {task_input}"],
                text=True,
                stderr=subprocess.STDOUT
            ).strip()
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
