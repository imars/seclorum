import sys
import time
import redis
import logging
import os
import argparse
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.memory.core import ConversationMemory

log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'worker_log.txt'))
logging.basicConfig(filename=log_path, level=logging.INFO)
logger = logging.getLogger("Worker")

class Worker(RedisMixin):
    def __init__(self, task_id, description, source, session_id):
        super().__init__(name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.source = source
        self.session_id = session_id
        self.memory = ConversationMemory(session_id)  # Initialize memory
        self.connect_redis()
        logger.info(f"Worker initialized for Task {task_id} in session {session_id}")
        self.memory.save(session_id=session_id, response=f"Worker initialized for Task {task_id}")

    def run(self):
        logger.info(f"Worker started for Task {self.task_id}: {self.description}")
        self.memory.save(prompt=f"Task {self.task_id}: {self.description}")  # Log task as prompt
        if "Old task to fail" in self.description:
            time.sleep(1)
            result = "Intentional failure for testing"
            status = "failed"
        else:
            if "haiku" in self.description.lower():
                result = "Soft winds whisper low\nBlossoms fade in twilight’s glow\nTime drifts ever on"
                time.sleep(3)
            elif "joke" in self.description.lower():
                result = "Why don’t skeletons fight?\n\nThey don’t have the guts!"
                time.sleep(2)
            elif "song" in self.description.lower():
                result = "(singing)\nFly me to the moon\nLet me play among the stars\nIn other words, hold my hand\n(end)"
                time.sleep(5)
            else:
                result = "Task completed generically"
                time.sleep(1)
            status = "completed"

        task_data = {
            "task_id": self.task_id,
            "description": self.description,
            "status": status,
            "result": result,
            "created_at": time.time()
        }
        self.store_data("tasks", {self.task_id: task_data})
        logger.info(f"Worker completed Task {self.task_id}: {result}")
        self.memory.save(response=f"Task {self.task_id} {status}: {result}")
        self.disconnect_redis()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker agent")
    parser.add_argument("task_id", type=str, help="Task ID")
    parser.add_argument("description", type=str, help="Task description")
    parser.add_argument("source", type=str, help="Task source")
    parser.add_argument("--session", type=str, required=True, help="Session ID")
    args = parser.parse_args()
    
    worker = Worker(args.task_id, args.description, args.source, args.session)
    worker.run()
