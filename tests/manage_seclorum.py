import sys
import time
import os
import signal
import subprocess
from seclorum.agents.master import MasterNode
from seclorum.web.app import app, socketio

FLASK_PID_FILE = "seclorum_flask.pid"
REDIS_PID_FILE = "seclorum_redis.pid"

def cleanup_existing_redis():
    """Kill any existing Redis on 6379."""
    try:
        redis_pids = subprocess.check_output(["lsof", "-i", ":6379", "-t"]).decode().strip().split()
        for pid in redis_pids:
            os.kill(int(pid), signal.SIGKILL)
            print(f"Killed existing Redis PID: {pid}")
        time.sleep(1)
    except subprocess.CalledProcessError:
        print("No existing Redis on 6379.")

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if action == "start":
        # Clean up any existing Redis once
        cleanup_existing_redis()

        # Start Redis
        redis_process = subprocess.Popen(["redis-stack-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        initial_pid = redis_process.pid
        print(f"Initial Redis PID from Popen: {initial_pid}")
        time.sleep(2)  # Wait for Redis to start
        if not os.system("redis-cli ping > /dev/null 2>&1"):
            print("Redis started successfully.")
            with open(REDIS_PID_FILE, "w") as f:
                f.write(str(initial_pid))  # Save initial PID (fallback used)
        else:
            print("Error: Redis failed to start.")
            redis_process.terminate()
            sys.exit(1)

        # Start Flask with MasterNode
        master_node = MasterNode()
        app.master_node = master_node
        master_node.start()
        print("Seclorum started. Running Flask app on http://127.0.0.1:5000...")
        with open(FLASK_PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        try:
            socketio.run(app, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            master_node.stop()
            os.remove(FLASK_PID_FILE)
            redis_process.terminate()
            os.remove(REDIS_PID_FILE)
            print("Seclorum stopped via Ctrl+C.")
    elif action == "stop":
        # Stop Flask
        if os.path.exists(FLASK_PID_FILE):
            with open(FLASK_PID_FILE, "r") as f:
                flask_pid = int(f.read().strip())
            try:
                os.kill(flask_pid, signal.SIGTERM)
                print(f"Sent shutdown signal to Flask (PID: {flask_pid}).")
                time.sleep(1)
                os.remove(FLASK_PID_FILE)
            except ProcessLookupError:
                print(f"No Flask process found with PID {flask_pid}.")
                os.remove(FLASK_PID_FILE)
            except Exception as e:
                print(f"Error stopping Flask: {e}")
        else:
            print("Flask not running (no PID file found).")

        # Stop Redis (rely on fallback)
        if os.path.exists(REDIS_PID_FILE):
            with open(REDIS_PID_FILE, "r") as f:
                redis_pid = int(f.read().strip())
            try:
                os.kill(redis_pid, signal.SIGTERM)
                print(f"Sent shutdown signal to Redis (PID: {redis_pid}).")
            except ProcessLookupError:
                print(f"No Redis process found with PID {redis_pid}.")
            os.remove(REDIS_PID_FILE)
        try:
            redis_pids = subprocess.check_output(["lsof", "-i", ":6379", "-t"]).decode().strip().split()
            if redis_pids:
                for pid in redis_pids:
                    os.kill(int(pid), signal.SIGKILL)
                print(f"Killed Redis PIDs on port 6379: {', '.join(redis_pids)}")
            os.remove(REDIS_PID_FILE) if os.path.exists(REDIS_PID_FILE) else None
        except subprocess.CalledProcessError:
            print("Redis not running on port 6379.")
        except Exception as e:
            print(f"Error in Redis shutdown: {e}")
    else:
        print("Usage: python tests/manage_seclorum.py [start|stop]")

if __name__ == "__main__":
    main()
