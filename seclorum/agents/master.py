import subprocess
import os
import sys
import signal
from flask_socketio import SocketIO
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.agents.lifecycle import LifecycleMixin
import logging
import threading
import time

class MasterNode(RedisMixin, LifecycleMixin):
    def __init__(self):
        RedisMixin.__init__(self, name="MasterNode")
        LifecycleMixin.__init__(self, name="MasterNode", pid_file="seclorum_master.pid")
        self.redis_available = False
        self.tasks = self.load_tasks() or {}
        self.socketio = SocketIO()
        self.active_workers = {}
        logging.basicConfig(filename='log.txt', level=logging.DEBUG)
        self.logger = logging.getLogger("MasterNode")
        self.running = False

    def start(self):
        if self.is_running():
            self.logger.info("MasterNode already running")
            return
        LifecycleMixin.start(self)
        try:
            self.connect_redis()
            self.redis_available = True
            self.logger.info("Redis connected")
        except Exception as e:
            self.logger.error(f"Redis unavailable at startup: {str(e)}. Running without Redis.")
            self.redis_available = False
        self.running = True
        threading.Thread(target=self.poll_tasks, daemon=True).start()
        self.logger.info("MasterNode started, checking stuck tasks")
        self.check_stuck_tasks()
        self.logger.info("MasterNode polling tasks")

    def stop(self):
        if not self.running:
            self.logger.info("MasterNode already stopped")
            return
        self.running = False
        for task_id, pid in self.active_workers.items():
            try:
                os.kill(pid, signal.SIGTERM)
                self.logger.info(f"Terminated worker for Task {task_id} (PID: {pid})")
            except ProcessLookupError:
                self.logger.info(f"Worker for Task {task_id} (PID: {pid}) already stopped")
        self.active_workers.clear()
        if self.redis_available:
            self.disconnect_redis()
        LifecycleMixin.stop(self)
        self.logger.info("MasterNode stopped")

    def process_task(self, task_id, description):
        task_id = str(task_id)
        self.tasks[task_id] = {"task_id": task_id, "description": description, "status": "assigned", "result": "", "created_at": time.time()}
        self.save_tasks()
        self.logger.info(f"Task {task_id} assigned: {description}")
        self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        self.logger.debug(f"Worker path resolved to: {worker_path}")
        if not os.path.exists(worker_path):
            self.logger.error(f"Worker script not found at {worker_path}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["result"] = "Worker script missing"
            self.save_tasks()
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
            return
        cmd = [sys.executable, worker_path, task_id, description, "WebUI"]
        self.logger.debug(f"Spawning worker with command: {' '.join(cmd)}")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(worker_path),
                env=env
            )
            self.active_workers[task_id] = process.pid
            self.logger.info(f"Spawned worker for Task {task_id} (PID: {process.pid})")
            stdout, stderr = process.communicate(timeout=15)
            if process.returncode != 0:
                self.logger.error(f"Worker for Task {task_id} failed with code {process.returncode}: stdout={stdout}, stderr={stderr}")
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["result"] = f"Worker error: {stderr or stdout}"
            else:
                self.logger.info(f"Worker for Task {task_id} completed: {stdout}")
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["result"] = stdout
            self.save_tasks()
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
            del self.active_workers[task_id]
        except subprocess.TimeoutExpired:
            self.logger.info(f"Worker for Task {task_id} still running after 15s")
        except Exception as e:
            self.logger.error(f"Failed to spawn worker for Task {task_id}: {str(e)}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["result"] = f"Worker spawn failed: {str(e)}"
            self.save_tasks()
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')

    def poll_tasks(self):
        while self.running:
            if not self.redis_available:
                self.logger.warning("Redis unavailable, polling skipped")
                time.sleep(1)
                continue
            redis_tasks = self.retrieve_data("tasks") or {}
            for task_id, task in redis_tasks.items():
                task_id = str(task_id)
                if task["status"] in ["completed", "failed"] and (task_id not in self.tasks or self.tasks[task_id]["status"] == "assigned"):
                    self.tasks[task_id] = task
                    self.save_tasks()
                    self.logger.info(f"Task {task_id} updated: {task['status']} - {task['result']}")
                    self.socketio.emit("task_update", task, namespace='/')
                    if task_id in self.active_workers:
                        del self.active_workers[task_id]
            time.sleep(1)

    def check_stuck_tasks(self):
        self.logger.info("Checking for stuck tasks")
        current_time = time.time()
        for task_id, task in list(self.tasks.items()):
            if task["status"] == "assigned" and (current_time - task["created_at"] > 30):
                task["status"] = "failed"
                task["result"] = "Worker failed to start or timed out"
                self.tasks[task_id] = task
                self.logger.warning(f"Marked Task {task_id} as failed: Worker never started or timed out")
                self.save_tasks()
                self.socketio.emit("task_update", task, namespace='/')

    def save_tasks(self):
        if self.redis_available:
            try:
                self.store_data("tasks", self.tasks)
            except Exception as e:
                self.logger.error(f"Failed to save tasks to Redis: {str(e)}")
                self.redis_available = False

    def load_tasks(self):
        if self.redis_available:
            try:
                return self.retrieve_data("tasks") or {}
            except Exception as e:
                self.logger.error(f"Failed to load tasks from Redis: {str(e)}")
                self.redis_available = False
        return {}
