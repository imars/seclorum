import subprocess
import os
import pickle
import signal
from flask_socketio import SocketIO
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.agents.lifecycle import LifecycleMixin
from seclorum.memory.core import ConversationMemory
import logging
import threading
import time

class MasterNode(RedisMixin, LifecycleMixin):
    def __init__(self, session_id="default_session"):
        RedisMixin.__init__(self, name="MasterNode")
        LifecycleMixin.__init__(self, name="MasterNode", pid_file="seclorum_master.pid")
        self.session_id = session_id
        self.memory = ConversationMemory(session_id)
        self.redis_available = False
        self.tasks = self.load_tasks() or {}
        self.socketio = SocketIO()  # Placeholder, initialized by app.py
        self.active_workers = {}
        self.logger = logging.getLogger("MasterNode")
        self.running = False
        self.logger.info(f"MasterNode initialized with session {session_id}")
        self.memory.save(session_id=session_id)

    def start(self):
        LifecycleMixin.start(self)
        try:
            self.connect_redis()
            self.redis_available = True
            self.logger.info("Redis connected successfully")
        except Exception as e:
            self.logger.error(f"Redis unavailable at startup: {str(e)}. Running without Redis.")
            self.redis_available = False
        self.running = True
        # Delay polling until socketio is initialized
        threading.Thread(target=self.poll_tasks, daemon=True).start()
        self.check_stuck_tasks()
        self.logger.info("MasterNode started and polling tasks")
        self.memory.save(response="MasterNode started and polling tasks")

    def stop(self):
        self.running = False
        for task_id, pid in self.active_workers.items():
            try:
                os.kill(pid, signal.SIGTERM)
                self.logger.info(f"Terminated worker for Task {task_id} (PID: {pid})")
                self.memory.save(response=f"Terminated worker for Task {task_id} (PID: {pid})")
            except ProcessLookupError:
                self.logger.info(f"Worker for Task {task_id} (PID: {pid}) already stopped")
                self.memory.save(response=f"Worker for Task {task_id} (PID: {pid}) already stopped")
        self.active_workers.clear()
        if self.redis_available:
            self.disconnect_redis()
        LifecycleMixin.stop(self)
        self.logger.info("MasterNode stopped")
        self.memory.save(response="MasterNode stopped")

    def process_task(self, task_id, description):
        task_id = str(task_id)
        self.tasks[task_id] = {"task_id": task_id, "description": description, "status": "assigned", "result": ""}
        self.save_tasks()
        self.logger.info(f"Task {task_id} assigned to WebUI: {description}")
        self.memory.save(prompt=f"Task {task_id}: {description}")
        if self.socketio.server:
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
        worker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "worker.py"))
        if not os.path.exists(worker_path):
            self.logger.error(f"Worker script not found at {worker_path}")
            self.memory.save(response=f"Error: Worker script not found at {worker_path}")
            return
        cmd = [os.sys.executable, worker_path, task_id, description, "WebUI", "--session", self.session_id]
        self.logger.debug(f"Spawning worker with command: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=os.environ.copy(),
                cwd=os.path.dirname(worker_path)
            )
            self.active_workers[task_id] = process.pid
            self.logger.info(f"Spawned session for WebUI on Task {task_id} (PID: {process.pid})")
            self.memory.save(response=f"Spawned worker for Task {task_id} (PID: {process.pid})")
            stdout, stderr = process.communicate(timeout=10)
            if process.returncode is not None:
                self.logger.error(f"Worker for Task {task_id} exited early with code {process.returncode}")
                self.logger.error(f"Worker stdout: {stdout}")
                self.logger.error(f"Worker stderr: {stderr}")
                self.memory.save(response=f"Worker for Task {task_id} failed: {stderr or stdout}")
                del self.active_workers[task_id]
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["result"] = stderr or stdout or "Worker crashed"
                self.save_tasks()
        except subprocess.TimeoutExpired:
            self.logger.info(f"Worker for Task {task_id} still running after 10s")
            self.memory.save(response=f"Worker for Task {task_id} still running after 10s")
        except Exception as e:
            self.logger.error(f"Failed to spawn worker for Task {task_id}: {str(e)}")
            self.memory.save(response=f"Failed to spawn worker for Task {task_id}: {str(e)}")
            self.tasks[task_id]["status"] = "failed"
            self.tasks[task_id]["result"] = str(e)
            self.save_tasks()

    def poll_tasks(self):
        while self.running:
            if not self.socketio.server:  # Wait for Flask to initialize socketio
                time.sleep(1)
                continue
            if not self.redis_available:
                for task_id, pid in list(self.active_workers.items()):
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        self.logger.info(f"Worker for Task {task_id} (PID: {pid}) completed or crashed")
                        self.memory.save(response=f"Task {task_id} assumed completed (no Redis)")
                        self.tasks[task_id]["status"] = "completed"
                        self.tasks[task_id]["result"] = "Completed (no Redis confirmation)"
                        del self.active_workers[task_id]
                        self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
                time.sleep(1)
                continue
            redis_tasks = self.retrieve_data("tasks") or {}
            self.logger.debug(f"Polling Redis tasks: {redis_tasks}")
            for task_id, task in redis_tasks.items():
                task_id = str(task_id)
                if task["status"] == "completed" and (task_id not in self.tasks or self.tasks[task_id]["status"] != "completed"):
                    self.tasks[task_id] = task
                    self.save_tasks()
                    self.logger.info(f"Task {task_id} completed: {task['result']}")
                    self.memory.save(response=f"Task {task_id} completed: {task['result']}")
                    self.socketio.emit("task_update", task, namespace='/')
                    if task_id in self.active_workers:
                        del self.active_workers[task_id]
            time.sleep(1)

    def check_stuck_tasks(self):
        if not self.redis_available:
            self.logger.warning("Redis unavailable, checking stuck tasks in memory only")
            for task_id, task in list(self.tasks.items()):
                if task["status"] == "assigned" and task_id not in self.active_workers:
                    task["status"] = "failed"
                    task["result"] = "Worker failed to start (Redis unavailable)"
                    self.tasks[task_id] = task
                    self.logger.warning(f"Marked Task {task_id} as failed: Worker never started (Redis unavailable)")
                    self.memory.save(response=f"Task {task_id} failed: Worker never started (Redis unavailable)")
                    if self.socketio.server:
                        self.socketio.emit("task_update", task, namespace='/')
            return
        redis_tasks = self.retrieve_data("tasks") or {}
        self.logger.debug(f"Checking stuck tasks. Current tasks: {self.tasks}, Redis tasks: {redis_tasks}")
        for task_id, task in list(self.tasks.items()):
            if task["status"] == "assigned" and task_id not in self.active_workers and task_id not in redis_tasks:
                task["status"] = "failed"
                task["result"] = "Worker failed to start"
                self.tasks[task_id] = task
                self.logger.warning(f"Marked Task {task_id} as failed: Worker never started")
                self.memory.save(response=f"Task {task_id} failed: Worker never started")
                self.save_tasks()
                if self.socketio.server:
                    self.socketio.emit("task_update", task, namespace='/')

    def save_tasks(self):
        if self.redis_available:
            self.store_data("tasks", self.tasks)
        else:
            self.logger.warning("Redis unavailable, tasks saved in memory only")

    def load_tasks(self):
        if self.redis_available:
            return self.retrieve_data("tasks")
        self.logger.warning("Redis unavailable, loading empty tasks")
        return {}
