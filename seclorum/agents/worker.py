import sys
import json
import os
import requests
from seclorum.agents.master import MasterNode

def log(message, log_file="worker_log.txt"):
    with open(log_file, "a") as f:
        f.write(f"Worker: {message}\n")

def call_ollama(task_id, description, model="deepseek-r1:8b"):
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": f"Perform this task: {description}",
        "stream": False
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json().get("response", "Task completed")
        return result.strip()
    except Exception as e:
        raise Exception(f"Ollama error: {str(e)}")

def run_worker(task_id, description, node_name):
    try:
        log(f"Started for Task {task_id}: {description}")
        result = call_ollama(task_id, description)
        log(f"Agent response for Task {task_id}: {result}")
        tasks_file = "MasterNode_tasks.json"
        if not os.path.exists(tasks_file):
            raise FileNotFoundError(f"{tasks_file} missing")
        with open(tasks_file, "r") as f:
            tasks = json.load(f)
        if str(task_id) not in tasks:
            raise ValueError(f"Task {task_id} not found in {tasks_file}")
        tasks[str(task_id)]["status"] = "completed"
        tasks[str(task_id)]["result"] = result
        with open(tasks_file, "w") as f:
            json.dump(tasks, f)
            f.flush()
        master = MasterNode()
        master.receive_update(node_name, f"{description} completed: {result}")
        log(f"Finished for Task {task_id}")
    except Exception as e:
        log(f"Error on Task {task_id}: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: worker.py <task_id> <description> <node_name>")
        sys.exit(1)
    run_worker(int(sys.argv[1]), sys.argv[2], sys.argv[3])
