# seclorum/agents/worker.py
import sys
import time
import redis
import logging
import os
import argparse
import ollama
import subprocess
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.agents.base import Agent

log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_log.txt'))
logger = logging.getLogger("Worker")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.handlers = [handler]
logger.propagate = False

class Worker(Agent, RedisMixin):
    def __init__(self, task_id, description, source, session_id, model="llama3.2:1b"):
        Agent.__init__(self, name=f"Worker_{task_id}", session_id=session_id)
        RedisMixin.__init__(self, name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.source = source
        self.model = model
        self.redis_available = False
        self.logger.debug("Debug logging active")
        try:
            self.connect_redis()
            self.redis_available = True
            self.logger.info("Redis connected successfully")
            self.logger.debug(f"Redis client type: {type(self.redis_client)}")
            self.memory.save(response="Redis connected successfully", task_id=self.task_id)
        except redis.ConnectionError as e:
            self.logger.error(f"Redis unavailable: {str(e)}. Running without Redis.")
            self.memory.save(response=f"Redis unavailable: {str(e)}", task_id=self.task_id)
        self.logger.info(f"Worker initialized for Task {self.task_id} in session {session_id}")
        self.memory.save(response=f"Worker initialized for Task {self.task_id}", task_id=self.task_id)

    def select_model(self, description):
        available_models = ["llama3.2:1b", "llama3.2:3b", "deepseek-r1:7b"]
        if self.model in available_models:
            return self.model
        return "llama3.2:1b"

    def process_task(self, task_id, description, execute_code=False):
        self.logger.info(f"Started processing Task {task_id}: {description}")
        self.memory.save(prompt=f"Task {task_id}: {description}", task_id=task_id)

        try:
            model = self.select_model(description)
            self.logger.debug(f"Selected model: {model}")
            prompt = f"Generate Python code to {description}. Return only the code."
            response = ollama.generate(model=model, prompt=prompt)
            result = response["response"].strip()
            self.logger.debug(f"Inference result: {result}")

            if execute_code:
                # Write code to a temp file and execute
                temp_file = f"temp_{task_id}.py"
                with open(temp_file, "w") as f:
                    f.write(result)
                try:
                    output = subprocess.check_output(["python", temp_file], stderr=subprocess.STDOUT, text=True)
                    self.logger.debug(f"Code execution output: {output}")
                    result = f"Code executed successfully:\n{result}\nOutput:\n{output}"
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Code execution failed: {e.output}")
                    result = f"Code execution failed:\n{result}\nError:\n{e.output}"
                finally:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)

            status = "completed"
            self.memory.save(response=f"Task {task_id} result: {result}", task_id=task_id)

        except Exception as e:
            result = f"Error processing task: {str(e)}"
            status = "failed"
            self.logger.error(f"Task {task_id} failed: {str(e)}")
            self.memory.save(response=result, task_id=task_id)

        task_data = {
            "task_id": task_id,
            "description": description,
            "status": status,
            "result": result,
            "created_at": time.time()
        }
        if self.redis_available:
            self.store_data("tasks", {task_id: task_data})
            self.logger.debug(f"Stored Task {task_id} data in Redis")
        else:
            self.logger.warning("Redis unavailable, task data stored in memory only")

        self.logger.info(f"Task {task_id} {status}: {result}")
        self.memory.save(response=f"Task {task_id} {status}: {result}", task_id=task_id)
        return status, result

    def start(self):
        self.logger.debug(f"Starting worker for Task {self.task_id}")
        status, result = self.process_task(self.task_id, self.description, execute_code=True)

    def stop(self):
        self.logger.debug(f"Stopping worker for Task {self.task_id}")
        if self.redis_available:
            self.disconnect_redis()
        self.logger.info(f"Worker for Task {self.task_id} stopped")
        self.memory.save(response=f"Worker for Task {self.task_id} stopped", task_id=self.task_id)

    def run(self):
        self.start()
        self.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker agent")
    parser.add_argument("task_id", type=str, help="Task ID")
    parser.add_argument("description", type=str, help="Task description")
    parser.add_argument("source", type=str, help="Task source")
    parser.add_argument("--session", type=str, required=True, help="Session ID")
    parser.add_argument("--model", type=str, default="llama3.2:1b", help="Model to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.handlers = [handler]
    else:
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(log_path)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.handlers = [handler]

    worker = Worker(args.task_id, args.description, args.source, args.session, model=args.model)
    if args.debug:
        logger.debug(f"Worker running in debug mode for Task {args.task_id}")
    worker.run()
