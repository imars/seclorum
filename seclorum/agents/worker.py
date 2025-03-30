import sys
import time
import redis
import logging
import os
import argparse
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.agents.base import Agent

# Configure logging with dynamic level based on --debug flag
log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_log.txt'))
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG if '--debug' in sys.argv else logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)
logger = logging.getLogger("Worker")

class Worker(Agent, RedisMixin):
    def __init__(self, task_id, description, source, session_id):
        # Initialize Agent with task-specific name and session_id
        Agent.__init__(self, name=f"Worker_{task_id}", session_id=session_id)
        RedisMixin.__init__(self, name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.source = source
        self.redis_available = False
        try:
            self.connect_redis()
            self.redis_available = True
            self.logger.info("Redis connected successfully")
            self.memory.save(response="Redis connected successfully")
        except redis.ConnectionError as e:
            self.logger.error(f"Redis unavailable: {str(e)}. Running without Redis.")
            self.memory.save(response=f"Redis unavailable: {str(e)}")
        self.logger.info(f"Worker initialized for Task {task_id} in session {session_id}")
        self.memory.save(response=f"Worker initialized for Task {task_id}")

    def process_task(self, task_id, description):
        """Process a task generically, with room for future inference logic."""
        self.logger.info(f"Started processing Task {task_id}: {description}")
        self.memory.save(prompt=f"Task {task_id}: {description}")

        try:
            # Placeholder for general-purpose task processing
            result = f"Processed task: {description}"
            time.sleep(1)  # Simulate some work
            status = "completed"
            self.logger.debug(f"Task {task_id} processing result: {result}")
            self.memory.save(response=f"Task {task_id} processing result: {result}")

        except Exception as e:
            result = f"Error processing task: {str(e)}"
            status = "failed"
            self.logger.error(f"Task {task_id} failed: {str(e)}")
            self.memory.save(response=f"Task {task_id} failed: {str(e)}")

        # Store task result, falling back to memory if Redis isn’t available
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
            # For now, rely on self.memory; could add local file fallback if needed

        self.logger.info(f"Task {task_id} {status}: {result}")
        self.memory.save(response=f"Task {task_id} {status}: {result}")
        return status, result

    def start(self):
        """Start the worker process."""
        self.logger.debug(f"Starting worker for Task {self.task_id}")
        status, result = self.process_task(self.task_id, self.description)

    def stop(self):
        """Stop the worker process and clean up."""
        self.logger.debug(f"Stopping worker for Task {self.task_id}")
        if self.redis_available:
            self.disconnect_redis()
        self.logger.info(f"Worker for Task {self.task_id} stopped")
        self.memory.save(response=f"Worker for Task {self.task_id} stopped")

    def run(self):
        """Entry point for worker execution."""
        self.start()
        self.stop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker agent")
    parser.add_argument("task_id", type=str, help="Task ID")
    parser.add_argument("description", type=str, help="Task description")
    parser.add_argument("source", type=str, help="Task source")
    parser.add_argument("--session", type=str, required=True, help="Session ID")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    worker = Worker(args.task_id, args.description, args.source, args.session)
    if args.debug:
        logger.debug(f"Worker running in debug mode for Task {args.task_id}")
    worker.run()
