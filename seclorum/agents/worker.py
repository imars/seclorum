import sys
import time
import redis
import logging
from seclorum.agents.redis_mixin import RedisMixin

logging.basicConfig(filename='worker_log.txt', level=logging.INFO)
logger = logging.getLogger("Worker")

class Worker(RedisMixin):
    def __init__(self, task_id, description, source):
        super().__init__(name=f"Worker_{task_id}")
        self.task_id = task_id
        self.description = description
        self.source = source
        self.connect_redis()

    def run(self):
        logger.info(f"Worker started for Task {self.task_id}: {self.description}")
        if "Old task to fail" in self.description:
            time.sleep(2)  # Shorten to beat check_stuck_tasks
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
        self.disconnect_redis()

if __name__ == "__main__":
    task_id, description, source = sys.argv[1], sys.argv[2], sys.argv[3]
    worker = Worker(task_id, description, source)
    worker.run()
