import sys
import subprocess
import os
import signal
import time
from seclorum.web.app import app, socketio

def start_seclorum():
    print("Seclorum started. Running Flask app on http://127.0.0.1:5000...")
    redis_process = subprocess.Popen(["redis-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"Initial Redis PID from Popen: {redis_process.pid}")
    time.sleep(2)  # Give Redis time to start
    try:
        subprocess.check_call(["redis-cli", "ping"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Redis started successfully.")
        print("Connected to Redis at localhost:6379")
    except subprocess.CalledProcessError:
        print("Failed to connect to Redis.")
        redis_process.terminate()
        return

    flask_process = subprocess.Popen([sys.executable, "-m", "flask", "run", "--host=127.0.0.1", "--port=5000"], env=os.environ.copy())
    with open("seclorum_flask.pid", "w") as f:
        f.write(str(flask_process.pid))
    with open("seclorum_redis.pid", "w") as f:
        f.write(str(redis_process.pid))

def stop_seclorum():
    try:
        with open("seclorum_flask.pid", "r") as f:
            flask_pid = int(f.read().strip())
            try:
                os.kill(flask_pid, signal.SIGTERM)
                print(f"Sent shutdown signal to Flask (PID: {flask_pid}).")
                time.sleep(1)  # Give it a sec to shut down
            except ProcessLookupError:
                print(f"Flask PID {flask_pid} not found—already stopped.")
    except FileNotFoundError:
        print("No Flask PID file found.")
    
    try:
        with open("seclorum_redis.pid", "r") as f:
            redis_pid = int(f.read().strip())
            try:
                os.kill(redis_pid, signal.SIGTERM)
                print(f"Sent shutdown signal to Redis (PID: {redis_pid}).")
                time.sleep(1)
                redis_pids = subprocess.check_output(["lsof", "-i", ":6379", "-t"]).decode().strip().split()
                for pid in redis_pids:
                    os.kill(int(pid), signal.SIGTERM)
                print(f"Killed Redis PIDs on port 6379: {' '.join(redis_pids)}")
            except ProcessLookupError:
                print(f"Redis PID {redis_pid} not found—already stopped.")
    except FileNotFoundError:
        print("No Redis PID file found.")
    except subprocess.CalledProcessError:
        print("No Redis processes found on port 6379.")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["start", "stop"]:
        print("Usage: python manage_seclorum.py [start|stop]")
        sys.exit(1)
    
    command = sys.argv[1]
    if command == "start":
        start_seclorum()
    elif command == "stop":
        stop_seclorum()
