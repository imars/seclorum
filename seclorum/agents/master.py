from .base import Agent
import subprocess
import json
import os
import time

class MasterNode(Agent):
    def __init__(self):
        super().__init__(name="MasterNode")
        self.nodes = {}
        self.sessions_file = "sessions.json"
        self.ollama_process = None
        self.start_ollama()
        if os.path.exists(self.sessions_file):
            with open(self.sessions_file, "r") as f:
                self.sessions = json.load(f)
        else:
            self.sessions = {}
        self.load_tasks()
        self.active_sessions = {}

    def start_ollama(self):
        try:
            subprocess.check_call(["ollama", "ps"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError:
            print("Starting Ollama server...")
            self.ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)
            print("Ollama started.")

    def stop_ollama(self):
        if self.ollama_process:
            print("Stopping Ollama server...")
            self.ollama_process.terminate()
            try:
                self.ollama_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ollama_process.kill()
            self.ollama_process = None

    def load_tasks(self):
        if os.path.exists("MasterNode_tasks.json"):
            with open("MasterNode_tasks.json", "r") as f:
                self.tasks = json.load(f)
        else:
            self.tasks = {}

    def save_tasks(self):
        with open("MasterNode_tasks.json", "w") as f:
            json.dump(self.tasks, f)

    def add_insight(self, insight):
        self.log_update(f"Insight: {insight}")
        print(f"DEBUG: Recorded insight - {insight}")

    def assign_task(self, task_id, description, node_name):
        task = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
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
        print(f"DEBUG: Updating status for {node_name} with {update}")
        for task_id, task in self.tasks.items():
            if task.get("node_name") == node_name or (node_name in self.nodes and self.nodes[node_name]["task_id"] == int(task_id)):
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = update.split(": ", 1)[-1] if ": " in update else update
                self.save_tasks()
                if str(task_id) in self.sessions:
                    self.log_update(f"Session for Task {task_id} completed (PID: {self.sessions[str(task_id)]['pid']})")
                print(f"DEBUG: Task {task_id} status set to completed")
                break
        else:
            print(f"No task found for node {node_name}")
        self.commit_changes(f"Update from {node_name}")

    def spawn_session(self, node_name, task_id, description):
        cmd = ["python", "seclorum/agents/worker.py", str(task_id), description, node_name]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.sessions[str(task_id)] = {"pid": proc.pid, "node_name": node_name, "description": description}
        self.active_sessions[str(task_id)] = proc
        self.save_tasks()
        self.log_update(f"Spawned session for {node_name} on Task {task_id} (PID: {proc.pid})")
        print(f"DEBUG: Spawned worker PID {proc.pid}")

    def check_sessions(self):
        completed = []
        for task_id, proc in list(self.active_sessions.items()):
            if proc.poll() is not None:
                print(f"DEBUG: Worker PID {proc.pid} finished for Task {task_id}")
                completed.append(task_id)
        for task_id in completed:
            del self.active_sessions[task_id]
        self.load_tasks()

    def get_session_status(self, task_id):
        self.load_tasks()
        task_id = str(task_id)
        if task_id in self.tasks:
            status = self.tasks[task_id]["status"]
            print(f"DEBUG: Status for Task {task_id} is {status}")
            return status
        return "not found"

    def __del__(self):
        self.stop_ollama()

if __name__ == "__main__":
    master = MasterNode()
    master.add_insight("redis-server not found; installed redis-stack instead")
    master.assign_task(1, "Design chat interface", "WebUI")
    master.receive_update("WebUI", "Chat interface mockup complete")
