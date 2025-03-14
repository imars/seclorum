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
        super().start()
        self.running = True
        threading.Thread(target=self.poll_tasks, daemon=True).start()
        self.logger.info("MasterNode started and polling tasks")

    def stop(self):
        self.running = False
        for task_id, pid in self.active_workers.items():
            try:
                os.kill(pid, signal.SIGTERM)
                self.logger.info(f"Terminated worker for Task {task_id} (PID: {pid})")
            except ProcessLookupError:
                self.logger.info(f"Worker for Task {task_id} (PID: {pid}) already stopped")
        self.active_workers.clear()
        super().stop()
        self.logger.info("MasterNode stopped")

    def process_task(self, task_id, description):
        task_id = str(task_id)
        self.tasks[task_id] = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
        self.save_tasks()
        self.logger.info(f"Task {task_id} assigned to WebUI")
        self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        cmd = [os.sys.executable, worker_path, task_id, description, "WebUI"]
        self.logger.debug(f"Spawning worker with command: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
                cwd=os.path.dirname(worker_path)  # Ensure correct working dir
            )
            self.active_workers[task_id] = process.pid
            self.logger.info(f"Spawned session for WebUI on Task {task_id} (PID: {process.pid})")
            # Check if worker starts
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode is not None:
                self.logger.error(f"Worker for Task {task_id} exited early with code {process.returncode}")
                self.logger.error(f"Worker stdout: {stdout}")
                self.logger.error(f"Worker stderr: {stderr}")
                del self.active_workers[task_id]
        except subprocess.TimeoutExpired:
            self.logger.info(f"Worker for Task {task_id} running normally after 10s")
        except Exception as e:
            self.logger.error(f"Failed to spawn worker for Task {task_id}: {str(e)}")

    def poll_tasks(self):
        while self.running:
            redis_tasks = self.retrieve_data("tasks") or {}
            self.logger.debug(f"Polling Redis tasks: {redis_tasks}")
            for task_id, task in redis_tasks.items():
                task_id = str(task_id)
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
