import sys
import time
import json
import os
from seclorum.agents.master import MasterNode

def log(message, log_file="worker_log.txt"):
    with open(log_file, "a") as f:
        f.write(f"Worker: {message}\n")

def run_worker(task_id, description, node_name):
    try:
        log(f"Started for Task {task_id}: {description}")
        time.sleep(2)
        log(f"Updating status for Task {task_id}")
        tasks_file = "MasterNode_tasks.json"
        if not os.path.exists(tasks_file):
            raise FileNotFoundError(f"{tasks_file} missing")
        with open(tasks_file, "r") as f:
            tasks = json.load(f)
        if str(task_id) not in tasks:
            raise ValueError(f"Task {task_id} not found in {tasks_file}")
        tasks[str(task_id)]["status"] = "completed"
        with open(tasks_file, "w") as f:
            json.dump(tasks, f)
            f.flush()
        master = MasterNode()
        master.receive_update(node_name, f"{description} completed")
        log(f"Finished for Task {task_id}")
    except Exception as e:
        log(f"Error on Task {task_id}: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: worker.py <task_id> <description> <node_name>")
        sys.exit(1)
    run_worker(int(sys.argv[1]), sys.argv[2], sys.argv[3])
