import sys
import time
import os
import signal
import subprocess
from seclorum.agents.master import MasterNode
from seclorum.web.app import app, socketio

FLASK_PID_FILE = "seclorum_flask.pid"
REDIS_PID_FILE = "seclorum_redis.pid"

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if action == "start":
        # Start Redis
        redis_process = subprocess.Popen(["redis-stack-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        redis_pid = redis_process.pid
        with open(REDIS_PID_FILE, "w") as f:
            f.write(str(redis_pid))
        time.sleep(2)  # Wait for Redis to start
        if not os.system("redis-cli ping > /dev/null 2>&1"):
            print("Redis started successfully.")
        else:
            print("Error: Redis failed to start.")
            redis_process.terminate()
            os.remove(REDIS_PID_FILE)
            sys.exit(1)

        # Start Flask with MasterNode
        master_node = MasterNode()
        app.master_node = master_node
        master_node.start()
        print("Seclorum started. Running Flask app on http://127.0.0.1:5000...")
        with open(FLASK_PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        try:
            socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
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

        # Stop Redis
        if os.path.exists(REDIS_PID_FILE):
            with open(REDIS_PID_FILE, "r") as f:
                redis_pid = int(f.read().strip())
            try:
                os.kill(redis_pid, signal.SIGTERM)
                print(f"Sent shutdown signal to Redis (PID: {redis_pid}).")
                time.sleep(1)
                os.remove(REDIS_PID_FILE)
            except ProcessLookupError:
                print(f"No Redis process found with PID {redis_pid}.")
                os.remove(REDIS_PID_FILE)
        # Fallback: Kill anything on 6379
        try:
            redis_pids = subprocess.check_output(["lsof", "-i", ":6379", "-t"]).decode().strip().split()
            if redis_pids:
                for pid in redis_pids:
                    os.kill(int(pid), signal.SIGKILL)
                print(f"Killed lingering Redis PIDs on port 6379: {', '.join(redis_pids)}")
            os.remove(REDIS_PID_FILE) if os.path.exists(REDIS_PID_FILE) else None
        except subprocess.CalledProcessError:
            print("Redis not running on port 6379.")
        except Exception as e:
            print(f"Error in Redis fallback shutdown: {e}")
    else:
        print("Usage: python tests/manage_seclorum.py [start|stop]")

if __name__ == "__main__":
    main()
