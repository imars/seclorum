import sys
import time
from seclorum.agents.master import MasterNode
from seclorum.web.app import app, socketio  # Import Flask app and SocketIO

def main():
    master_node = MasterNode()
    app.master_node = master_node  # Attach to app for routes to use
    action = sys.argv[1] if len(sys.argv) > 1 else "start"
    if action == "start":
        master_node.start()
        print("Seclorum started. Running Flask app on http://127.0.0.1:5000...")
        try:
            socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
        except KeyboardInterrupt:
            master_node.stop()
            print("Seclorum stopped via Ctrl+C.")
    elif action == "stop":
        master_node.stop()
        print("Seclorum stopped.")
    else:
        print("Usage: python tests/manage_seclorum.py [start|stop]")

if __name__ == "__main__":
    main()
