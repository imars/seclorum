import sys
import time
import subprocess
import os
from seclorum.agents.base import Agent
from seclorum.agents.lifecycle import LifecycleMixin
import logging
from seclorum.agents.redis_mixin import RedisMixin

log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_log.txt'))
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filemode='a',
    force=True
)

class Worker(Agent, LifecycleMixin, RedisMixin):
    def __init__(self, task_id, description, node_name):
        Agent.__init__(self, name=f"Worker_{task_id}")
        LifecycleMixin.__init__(self, name=f"Worker_{task_id}", pid_file=f"seclorum_worker_{task_id}.pid")
        RedisMixin.__init__(self, name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.node_name = node_name
        self.model = "deepseek-r1:8b" if description.startswith("[complex]") else "llama3.2:latest"
        self.logger = logging.getLogger(self.name)
        self.logger.info(f"Worker initialized for Task {task_id} with {self.model} from: {os.path.abspath(__file__)}")
        self.process = None

    def start(self):
        LifecycleMixin.start(self)
        self.connect_redis()
        self.log_update("Starting worker")
        try:
            self.process_task(self.task_id, self.description)
        except Exception as e:
            self.logger.error(f"Unexpected error in task processing: {str(e)}")
            self.report_result(f"Failed: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    self.logger.info(f"Terminated subprocess for Task {self.task_id} (PID: {self.process.pid})")
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.logger.info(f"Killed subprocess for Task {self.task_id} (PID: {self.process.pid}) after timeout")
            else:
                self.logger.info(f"Subprocess for Task {self.task_id} (PID: {self.process.pid}) already completed")
        self.disconnect_redis()
        LifecycleMixin.stop(self)
        self.log_update(f"Worker stopped for Task {self.task_id}")

    def process_task(self, task_id, description):
        self.logger.info(f"Processing task {task_id}: {description}")
        task_input = description.replace("[complex]", "").strip()

        for attempt in range(3):
            try:
                subprocess.check_call(["ollama", "ps"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.logger.info(f"Ollama is running on attempt {attempt + 1}")
                break
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Ollama not responding on attempt {attempt + 1}: {str(e)}")
                time.sleep(2 ** attempt)
        else:
            result = "Failed: Ollama server not available after 3 attempts"
            self.logger.error(result)
            self.report_result(result)
            return

        try:
            self.process = subprocess.Popen(
                ["ollama", "run", self.model, f"Respond to this task: {task_input}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = self.process.communicate(timeout=60)
            if self.process.returncode == 0:
                result = stdout.strip()
                self.logger.info(f"Task completed successfully: {result}")
            else:
                result = f"Error processing task with Ollama ({self.model}): {stderr.strip()}"
                self.logger.error(result)
        except subprocess.TimeoutExpired:
            self.process.kill()
            result = f"Task timed out after 60s with {self.model}"
            self.logger.error(result)
        except subprocess.CalledProcessError as e:
            result = f"Subprocess error with Ollama ({self.model}): {e.output}"
            self.logger.error(result)
        except Exception as e:
            result = f"Unexpected processing error: {str(e)}"
            self.logger.error(result)
        self.report_result(result)

    def report_result(self, result):
        try:
            tasks = self.retrieve_data("tasks") or {}
            tasks[self.task_id] = {"task_id": self.task_id, "description": self.description, "status": "completed", "result": result}
            self.store_data("tasks", tasks)
            self.logger.info(f"Updated task {self.task_id} in Redis: {tasks[self.task_id]}")
            self.commit_changes(f"Task {self.task_id} result: {result}")
        except Exception as e:
            self.logger.error(f"Failed to report result: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python worker.py <task_id> <description> <node_name>")
        logging.error("Invalid arguments provided")
        sys.exit(1)
    task_id, description, node_name = sys.argv[1], sys.argv[2], sys.argv[3]
    worker = Worker(task_id, description, node_name)
    worker.start()
