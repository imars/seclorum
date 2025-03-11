import os
import time
import subprocess
import json
import requests
import sys
from seclorum.utils.logger import ConversationLogger

def kill_existing_server():
    print("Killing existing server...")
    cmd = "lsof -i :5000 | grep LISTEN | awk '{print $2}' | sort -u | xargs -r kill -9"
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
        response = requests.get("http://127.0.0.1:5000/", timeout=5)
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

def check_outputs(expected_task_id, expected_description, logger):
    print("Checking outputs...")
    with open("log.txt", "r") as f:
        log_content = f.read()
    print(f"log.txt content:\n{log_content}")
    assert f"Task {expected_task_id} assigned to WebUI" in log_content, "Task assignment missing"
    assert f"Spawned session for WebUI on Task {expected_task_id}" in log_content, "Session spawn missing"
    assert f"Received update from WebUI: {expected_description} completed" in log_content, "Update missing"

    with open("MasterNode_tasks.json", "r") as f:
        tasks = json.load(f)
    print(f"MasterNode_tasks.json content:\n{tasks}")
    assert str(expected_task_id) in tasks, f"Task {expected_task_id} not in tasks"
    assert tasks[str(expected_task_id)]["description"] == expected_description, "Wrong description"
    assert tasks[str(expected_task_id)]["status"] == "completed", "Status not completed"

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
        for file in ["log.txt", "MasterNode_tasks.json", "sessions.json", "project/changes.txt"]:
            if os.path.exists(file):
                os.remove(file)
        convo_file = os.path.join("logs/conversations", f"conversation_{chat_id}.json")
        if os.path.exists(convo_file):
            os.remove(convo_file)
        if os.path.exists("project"):
            subprocess.run(["rm", "-rf", "project"])

        proc = run_app_in_background()
        task_id = 1
        task_description = "Build feature"
        submit_task(task_description, logger)

        print("Waiting for worker to complete...")
        time.sleep(1)  # Reduced since spawn_session waits

        from seclorum.agents.master import MasterNode
        master = MasterNode()
        status = master.get_session_status(task_id)
        print(f"Session status for Task {task_id}: {status}")
        logger.log_response(f"Session status: {status}")
        assert status == "completed", f"Expected completed, got {status}"

        check_outputs(task_id, task_description, logger)
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
