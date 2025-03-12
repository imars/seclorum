import os
import time
import subprocess
import json
import requests
import sys
from seclorum.utils.logger import ConversationLogger

def kill_existing_server():
    print("Killing existing server...")
    cmd = "lsof -i :5000 | grep LISTEN | awk '{print }' | sort -u | xargs -r kill -9"
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = result.stdout.decode(), result.stderr.decode()
    print(f"Kill result: stdout={stdout}, stderr={stderr}")
    time.sleep(1)
    check = subprocess.run("lsof -i :5000", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check.stdout.decode().strip():
        raise RuntimeError(f"Port 5000 still in use: {check.stdout.decode()}")

def run_app_in_background():
    print("Starting Flask app in background...")
    proc = subprocess.Popen(
        ["python", "run.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(3)
    try:
        response = requests.get("http://127.0.0.1:5000/chat", timeout=5)  # Changed to /chat
        print(f"Server check response: {response.status_code}")
    except requests.RequestException as e:
        stdout, stderr = proc.communicate(timeout=5)
        raise RuntimeError(f"Server not responding: {e}\nStdout: {stdout}\nStderr: {stderr}")
    return proc

def submit_task(task_description, logger):
    prompt = f"Submit task: {task_description}"
    print(f"Submitting task: {task_description}")
    logger.log_prompt(prompt)
    url = "http://127.0.0.1:5000/chat"
    data = {"task": task_description}
    try:
        response = requests.post(url, data=data, timeout=5)
        print(f"Task submission response: {response.text}")
        logger.log_response(response.text)
        time.sleep(1)
        return response
    except requests.RequestException as e:
        print(f"Task submission failed: {e}")
        logger.log_response(f"Failed: {e}")
        raise

def check_outputs(expected_task_ids, expected_descriptions, logger):
    print("Checking outputs...")
    with open("log.txt", "r") as f:
        log_content = f.read()
    print(f"log.txt content:\n{log_content}")
    for tid, desc in zip(expected_task_ids, expected_descriptions):
        assert f"Task {tid} assigned to WebUI" in log_content, f"Task {tid} assignment missing"
        assert f"Spawned session for WebUI on Task {tid}" in log_content, f"Session spawn for {tid} missing"
        assert f"Received update from WebUI: {desc} completed" in log_content, f"Update for {tid} missing"

    with open("MasterNode_tasks.json", "r") as f:
        tasks = json.load(f)
    print(f"MasterNode_tasks.json content:\n{tasks}")
    for tid, desc in zip(expected_task_ids, expected_descriptions):
        tid_str = str(tid)
        assert tid_str in tasks, f"Task {tid} not in tasks"
        assert tasks[tid_str]["description"] == desc, f"Wrong description for {tid}"
        assert tasks[tid_str]["status"] == "completed", f"Status not completed for {tid}"

    with open("project/changes.txt", "r") as f:
        changes = f.read()
    print(f"project/changes.txt content:\n{changes}")
    assert "MasterNode: Update from WebUI" in changes, "Changes file missing update"

    git_log = subprocess.run(
        ["git", "--git-dir=project/.git", "log", "--oneline"],
        capture_output=True, text=True
    ).stdout
    print(f"Git log content:\n{git_log}")
    assert "Update changes.txt" in git_log, "Git commit missing"

def test_seclorum_workflow():
    chat_id = "2025-03-11-1"
    logger = ConversationLogger(chat_id)
    try:
        kill_existing_server()
        print("Cleaning up previous files...")
        for file in ["log.txt", "MasterNode_tasks.json", "sessions.json", "project/changes.txt", "worker_log.txt"]:
            if os.path.exists(file):
                os.remove(file)
        convo_file = os.path.join("logs/conversations", f"conversation_{chat_id}.json")
        if os.path.exists(convo_file):
            os.remove(convo_file)
        if os.path.exists("project"):
            subprocess.run(["rm", "-rf", "project"])

        proc = run_app_in_background()
        task_ids = [1, 2]
        task_descriptions = ["Build feature", "Test feature"]
        for desc in task_descriptions:
            submit_task(desc, logger)

        print("Waiting for workers to complete...")
        time.sleep(5)  # Give both workers time

        from seclorum.agents.master import MasterNode
        master = MasterNode()
        master.check_sessions()  # Poll for completion
        for tid in task_ids:
            status = master.get_session_status(tid)
            print(f"Session status for Task {tid}: {status}")
            logger.log_response(f"Session status: {status}")
            assert status == "completed", f"Expected completed, got {status}"

        check_outputs(task_ids, task_descriptions, logger)
        print("Test passed!")
        logger.log_response("Test passed!")
    except Exception as e:
        print(f"Test failed with error: {e}")
        logger.log_response(f"Test failed: {e}")
        if 'proc' in locals():
            stdout, stderr = proc.communicate(timeout=5)
            print(f"Server stdout after failure: {stdout}")
            print(f"Server stderr after failure: {stderr}")
        sys.exit(1)
    finally:
        print("Cleaning up...")
        if 'proc' in locals():
            proc.terminate()
            kill_existing_server()
        sys.exit(0)

if __name__ == "__main__":
    test_seclorum_workflow()
