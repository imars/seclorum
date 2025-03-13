import sys
import os
import importlib.util
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from .base import Agent
from .redis_mixin import RedisMixin
import subprocess
import json
import time

class MasterNode(Agent, RedisMixin):
    def __init__(self):
        Agent.__init__(self, name="MasterNode")
        RedisMixin.__init__(self)
        self.nodes = {}
        self.active_sessions = {}
        self.sessions = {}
        self.load_tasks()
        self.load_sessions()

    def start(self):
        self.connect_redis()
        self.check_sessions()
        self.log_update("MasterNode started")

    def stop(self):
        for task_id, proc in list(self.active_sessions.items()):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    del self.active_sessions[task_id]
        self.save_tasks()
        self.save_sessions()
        self.disconnect_redis()
        self.log_update("MasterNode stopped")

    def load_tasks(self):
        self.tasks = self.retrieve_data("MasterNode_tasks") or {}

    def save_tasks(self):
        self.store_data("MasterNode_tasks", self.tasks)

    def load_sessions(self):
        self.sessions = self.retrieve_data("MasterNode_sessions") or {}

    def save_sessions(self):
        self.store_data("MasterNode_sessions", self.sessions)

    def assign_task(self, task_id, description, node_name):
        task = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
        self.tasks[str(task_id)] = task
        self.nodes[node_name] = task
        self.save_tasks()
        self.log_update(f"Task {task_id} assigned to {node_name}")
        self.spawn_session(node_name, task_id, description)

    def process_task(self, task_id, description):
        self.assign_task(task_id, description, "WebUI")

    def receive_update(self, node_name, update):
        self.log_update(f"Received update from {node_name}: {update}")
        for task_id, task in self.tasks.items():
            if task.get("node_name") == node_name or (node_name in self.nodes and self.nodes[node_name]["task_id"] == int(task_id)):
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = update.split(": ", 1)[-1] if ": " in update else update
                self.save_tasks()
                break
        self.commit_changes(f"Update from {node_name}")

    def spawn_session(self, node_name, task_id, description):
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        cmd = [sys.executable, worker_path, str(task_id), description, node_name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.sessions[str(task_id)] = {"pid": proc.pid, "node_name": node_name, "description": description}
        self.active_sessions[str(task_id)] = proc
        self.save_tasks()
        self.save_sessions()
        self.log_update(f"Spawned session for {node_name} on Task {task_id} (PID: {proc.pid})")

    def check_sessions(self):
        completed = []
        for task_id, proc in list(self.active_sessions.items()):
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                completed.append(task_id)
        for task_id in completed:
            del self.active_sessions[task_id]
        self.load_tasks()

    def get_session_status(self, task_id):
        self.load_tasks()
        task_id = str(task_id)
        if task_id in self.tasks:
            return self.tasks[task_id]["status"]
        return "not found"

if __name__ == "__main__":
    master = MasterNode()
    master.start()
    master.assign_task(1, "Design chat interface", "WebUI")
    master.receive_update("WebUI", "Chat interface mockup complete")
    master.stop()
