import subprocess
import os
import pickle
import signal
from flask_socketio import SocketIO
from seclorum.agents.redis_mixin import RedisMixin
import logging
import threading
import time

class MasterNode(RedisMixin):
    def __init__(self):
        super().__init__(name="MasterNode", pid_file="seclorum_master.pid")
        self.tasks = self.load_tasks() or {}
        self.socketio = SocketIO()
        self.active_workers = {}
        logging.basicConfig(filename='app.log', level=logging.DEBUG)
        self.logger = logging.getLogger("MasterNode")
        self.running = False

    def start(self):
        """Start the MasterNode."""
        super().start()
        self.running = True
        threading.Thread(target=self.poll_tasks, daemon=True).start()

    def stop(self):
        """Stop the MasterNode and its workers."""
        self.running = False
        for task_id, pid in self.active_workers.items():
            try:
                os.kill(pid, signal.SIGTERM)
                self.logger.info(f"Terminated worker for Task {task_id} (PID: {pid})")
            except ProcessLookupError:
                self.logger.info(f"Worker for Task {task_id} (PID: {pid}) already stopped")
        self.active_workers.clear()
        super().stop()

    def process_task(self, task_id, description):
        self.tasks[str(task_id)] = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
        self.save_tasks()
        self.logger.info(f"Task {task_id} assigned to WebUI")
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        cmd = [os.sys.executable, worker_path, str(task_id), description, "WebUI"]
        self.logger.debug(f"Spawning worker with command: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())
            self.active_workers[task_id] = process.pid
            self.logger.info(f"Spawned session for WebUI on Task {task_id} (PID: {process.pid})")
        except Exception as e:
            self.logger.error(f"Failed to spawn worker for Task {task_id}: {str(e)}")

    def poll_tasks(self):
        while self.running:
            tasks = self.retrieve_data("tasks") or {}
            for task_id, task in tasks.items():
                if task["status"] == "completed" and (task_id not in self.tasks or self.tasks[task_id]["status"] != "completed"):
                    self.tasks[task_id] = task
                    self.save_tasks()
                    self.logger.info(f"Task {task_id} completed: {task['result']}")
                    self.socketio.emit("task_update", task, namespace='/')
                    if task_id in self.active_workers:
                        del self.active_workers[task_id]
            time.sleep(1)

    def save_tasks(self):
        self.store_data("tasks", self.tasks)

    def load_tasks(self):
        return self.retrieve_data("tasks")
