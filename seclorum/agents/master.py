import subprocess
import os
import redis
import pickle

class MasterNode:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
        self.tasks = self.load_tasks()

    def start(self):
        print("MasterNode: MasterNode started")
        self.save_tasks()

    def process_task(self, task_id, description):
        self.tasks[str(task_id)] = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
        self.save_tasks()
        print(f"MasterNode: Task {task_id} assigned to WebUI")
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        print(f"MasterNode: Spawning worker at: {worker_path}")
        process = subprocess.Popen([os.sys.executable, worker_path, str(task_id), description, "WebUI"])
        print(f"MasterNode: Spawned session for WebUI on Task {task_id} (PID: {process.pid})")

    def receive_update(self, node_name, message):
        parts = message.split(":", 1)
        if len(parts) == 2 and parts[0].startswith("Task "):
            task_id = parts[0].split(" ")[1]
            result = parts[1].strip()
            if task_id in self.tasks:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = result
                self.save_tasks()
                print(f"MasterNode: Received update from {node_name}: Task {task_id} completed: {result}")
                print(f"MasterNode: Committed changes: Update from {node_name}")

    def save_tasks(self):
        self.redis_client.set("tasks", pickle.dumps(self.tasks))

    def load_tasks(self):
        tasks_data = self.redis_client.get("tasks")
        return pickle.loads(tasks_data) if tasks_data else {}
