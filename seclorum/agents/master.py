from .base import Agent
import subprocess
import json
import os

class MasterNode(Agent):
    def __init__(self):
        super().__init__(name="MasterNode")
        self.nodes = {}
        self.sessions_file = "sessions.json"
        if os.path.exists(self.sessions_file):
            with open(self.sessions_file, "r") as f:
                self.sessions = json.load(f)
        else:
            self.sessions = {}  # {task_id: {"pid": int, "node_name": str, "description": str}}
        if os.path.exists("MasterNode_tasks.json"):
            with open("MasterNode_tasks.json", "r") as f:
                self.tasks = json.load(f)
        else:
            self.tasks = {}

    def save_sessions(self):
        with open(self.sessions_file, "w") as f:
            json.dump(self.sessions, f)

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
        for task_id, task in self.tasks.items():
            if task.get("node_name") == node_name or (node_name in self.nodes and self.nodes[node_name]["task_id"] == int(task_id)):
                self.tasks[task_id]["status"] = "completed"
                self.save_tasks()
                if str(task_id) in self.sessions:
                    self.log_update(f"Session for Task {task_id} completed (PID: {self.sessions[str(task_id)]['pid']})")
                break
        else:
            print(f"No task found for node {node_name}")
        self.commit_changes(f"Update from {node_name}")

    def spawn_session(self, node_name, task_id, description):
        cmd = ["python", "seclorum/agents/worker.py", str(task_id), description, node_name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.sessions[str(task_id)] = {"pid": proc.pid, "node_name": node_name, "description": description}
        self.save_sessions()
        self.log_update(f"Spawned session for {node_name} on Task {task_id} (PID: {proc.pid})")
        self.tasks[str(task_id)]["node_name"] = node_name
        self.save_tasks()

    def get_session_status(self, task_id):
        task_id = str(task_id)
        if task_id in self.sessions:
            pid = self.sessions[task_id]["pid"]
            proc = subprocess.Popen(["ps", "-p", str(pid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            is_alive = proc.returncode == 0 and str(pid) in stdout.decode()
            return "running" if is_alive else "completed"
        return "not found"

if __name__ == "__main__":
    master = MasterNode()
    master.assign_task(1, "Design chat interface", "WebUI")
    master.receive_update("WebUI", "Chat interface mockup complete")
