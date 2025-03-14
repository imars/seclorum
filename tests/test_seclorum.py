import subprocess
import time
import requests
import socketio
import logging
import os
from threading import Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestSeclorum")

class TestSeclorum:
    def __init__(self):
        self.base_url = "http://127.0.0.1:5000"
        self.redis_proc = None
        self.app_proc = None
        self.sio = socketio.Client()
        self.task_results = {}
        self.task_ids = {}
        self.project_root = "/Users/ian/dev/projects/agents/local/seclorum"

    def start_redis(self):
        logger.info("Starting Redis...")
        self.redis_proc = subprocess.Popen(
            ["redis-server", "--daemonize", "yes"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(1)
        result = subprocess.run(["redis-cli", "ping"], capture_output=True, text=True)
        if result.stdout.strip() != "PONG":
            logger.error("Redis failed to start")
            raise RuntimeError("Redis ping failed")
        logger.info("Redis started successfully")

    def start_app(self):
        logger.info("Starting Seclorum app...")
        env = os.environ.copy()
        env["PYTHONPATH"] = self.project_root
        self.app_proc = subprocess.Popen(
            ["python", "seclorum/cli/commands.py", "start"],
            cwd=self.project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        for _ in range(10):
            try:
                response = requests.get(f"{self.base_url}/chat", timeout=2)
                if response.status_code == 200:
                    logger.info("App started successfully")
                    return
            except requests.ConnectionError:
                time.sleep(2)
        logger.error("App failed to start after 20 seconds")
        raise RuntimeError("App startup failed")

    def stop_processes(self):
        logger.info("Stopping app and Redis...")
        # Send a final request to trigger check_stuck_tasks
        try:
            requests.get(f"{self.base_url}/chat", timeout=2)
            time.sleep(2)  # Give it a moment to process
        except requests.ConnectionError:
            logger.warning("Could not trigger final check_stuck_tasks")
        if self.app_proc:
            env = os.environ.copy()
            env["PYTHONPATH"] = self.project_root
            subprocess.run(
                ["python", "seclorum/cli/commands.py", "stop"],
                cwd=self.project_root,
                env=env
            )
            self.app_proc.wait()
            logger.info("App stopped")
        if self.redis_proc:
            subprocess.run(["redis-cli", "shutdown"])
            self.redis_proc.wait()
            logger.info("Redis stopped")

    def setup_socketio(self):
        @self.sio.event
        def connect():
            logger.info("SocketIO connected")

        @self.sio.event
        def disconnect():
            logger.info("SocketIO disconnected")

        @self.sio.event
        def task_update(data):
            logger.info(f"Task update received: {data}")
            task_id = data["task_id"]
            if data["status"] == "assigned" and task_id not in self.task_ids.values():
                for task, tid in self.task_ids.items():
                    if not tid and data["description"] == task:
                        self.task_ids[task] = task_id
            self.task_results[task_id] = data

        self.sio.connect(self.base_url)
        Thread(target=self.sio.wait, daemon=True).start()

    def submit_task(self, task_description):
        logger.info(f"Submitting task: {task_description}")
        response = requests.post(
            f"{self.base_url}/chat",
            data={"task": task_description},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code not in [200, 302]:
            logger.error(f"Task submission failed: {response.text[:200]}...")
            return None
        return None  # ID set via task_update

    def check_dashboard(self):
        logger.info("Checking dashboard...")
        response = requests.get(f"{self.base_url}/dashboard")
        if response.status_code == 200:
            logger.info(f"Dashboard response: {response.text[:200]}...")
        else:
            logger.error(f"Dashboard check failed: {response.status_code}")

    def run_test(self):
        try:
            self.start_redis()
            self.start_app()
            self.setup_socketio()

            tasks = [
                "Write a haiku",
                "Tell a joke",
                "Sing a song",
                "Old task to fail"
            ]
            self.task_ids = {task: None for task in tasks}
            for task in tasks:
                self.submit_task(task)
                time.sleep(1)

            time.sleep(45)

            self.check_dashboard()
            for task, task_id in self.task_ids.items():
                if task_id in self.task_results:
                    result = self.task_results[task_id]
                    logger.info(f"Task '{task}' (ID: {task_id}) status: {result['status']}, result: {result['result']}")
                else:
                    logger.warning(f"Task '{task}' (ID: {task_id or 'unknown'}) not completed or failed silently")

        except Exception as e:
            logger.error(f"Test failed: {str(e)}")
        finally:
            self.stop_processes()
            self.sio.disconnect()

if __name__ == "__main__":
    test = TestSeclorum()
    test.run_test()
