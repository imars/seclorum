from .base import Agent
import subprocess
import json
import os

class MasterNode(Agent):
    def __init__(self):
        super().__init__(name="MasterNode")
        self.nodes = {}
        if os.path.exists("MasterNode_tasks.json"):
            with open("MasterNode_tasks.json", "r") as f:
                self.tasks = json.load(f)
        else:
            self.tasks = {}

    def assign_task(self, task_id, description, node_name):
        task = {"task_id": task_id, "description": description, "status": "assigned"}
        self.tasks[str(task_id)] = task
        self.nodes[node_name] = task
        self.save_tasks()
        self.log_update(f"Task {task_id} assigned to {node_name}")
        print(f"Task {task_id} assigned to {node_name}")
        self.spawn_session(node_name, task_id, description)

    def process_task(self, task_id, description):
        self.assign_task(task_id, description, "WebUI")

    def receive_update(self, node_name, update):
        self.log_update(f"Received update from {node_name}: {update}")
        # Find task by node_name or update all matching tasks
        for task_id, task in self.tasks.items():
            if task.get("node_name") == node_name or (node_name in self.nodes and self.nodes[node_name]["task_id"] == int(task_id)):
                self.tasks[task_id]["status"] = "completed"
                self.save_tasks()
                break
        else:
            print(f"No task found for node {node_name}")
        self.commit_changes(f"Update from {node_name}")

    def spawn_session(self, node_name, task_id, description):
        cmd = f"echo 'Simulating {node_name} working on Task {task_id}: {description}' >> worker_log.txt"
        subprocess.run(cmd, shell=True)
        self.log_update(f"Spawned session for {node_name} on Task {task_id}")
        # Store node_name in task for later lookup
        if str(task_id) in self.tasks:
            self.tasks[str(task_id)]["node_name"] = node_name
            self.save_tasks()

if __name__ == "__main__":
    master = MasterNode()
    master.assign_task(1, "Design chat interface", "WebUI")
    master.receive_update("WebUI", "Chat interface mockup complete")
