import sys
import time
import os
import signal
from seclorum.agents.master import MasterNode
from seclorum.web.app import app, socketio

PID_FILE = "seclorum.pid"

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    
    if action == "start":
        master_node = MasterNode()
        app.master_node = master_node
        master_node.start()
        print("Seclorum started. Running Flask app on http://127.0.0.1:5000...")
        # Save PID
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        try:
            socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            master_node.stop()
            os.remove(PID_FILE)
            print("Seclorum stopped via Ctrl+C.")
    elif action == "stop":
        if not os.path.exists(PID_FILE):
            print("Seclorum not running (no PID file found).")
            return
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)  # Send SIGTERM to trigger cleanup
            print(f"Sent shutdown signal to Seclorum (PID: {pid}).")
            time.sleep(1)  # Give it a moment to shut down
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except ProcessLookupError:
            print(f"No process found with PID {pid}. Cleaning up PID file.")
            os.remove(PID_FILE)
        except Exception as e:
            print(f"Error stopping Seclorum: {e}")
    else:
        print("Usage: python tests/manage_seclorum.py [start|stop]")

if __name__ == "__main__":
    main()
