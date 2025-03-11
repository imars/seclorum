import sys
import time
from seclorum.agents.master import MasterNode

def run_worker(task_id, description, node_name):
    print(f"Worker {node_name} processing Task {task_id}: {description}")
    # Simulate work
    time.sleep(2)
    master = MasterNode()
    master.receive_update(node_name, f"{description} completed")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: worker.py <task_id> <description> <node_name>")
        sys.exit(1)
    run_worker(int(sys.argv[1]), sys.argv[2], sys.argv[3])
