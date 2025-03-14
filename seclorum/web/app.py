from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from seclorum.agents.master import MasterNode
import logging
import sys
import signal
import time

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app)
app.master_node = None
logging.basicConfig(filename='app.log', level=logging.DEBUG)

def get_master_node():
    global app
    if app.master_node is None:
        app.master_node = MasterNode()
        app.master_node.socketio = socketio
    return app.master_node

def run_app():
    master = get_master_node()
    master.start()
    socketio.emit("debug", {"message": "Server started"})
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    master = get_master_node()
    if not master.is_running():
        master.start()
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = str(int(time.time() * 1000))  # Unique timestamp-based ID
            master.process_task(task_id, task_description)
            return redirect(url_for("chat"))
    return render_template("chat.html", tasks=master.tasks)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/dashboard")
def dashboard():
    master = get_master_node()
    if not master.is_running():
        master.start()
    return render_template("dashboard.html", tasks=master.tasks)

@app.route("/delete_task/<task_id>", methods=["POST"])
def delete_task(task_id):
    master = get_master_node()
    if task_id in master.tasks:
        del master.tasks[task_id]
        master.save_tasks()
        return redirect(url_for("dashboard"))
    return redirect(url_for("dashboard"))

def shutdown_handler(signum, frame):
    master = get_master_node()
    master.stop()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        master = get_master_node()
        if master.is_running():
            master.stop()
            print("MasterNode stopped via CLI")
        else:
            print("MasterNode is not running")
    else:
        run_app()
EOFcat << 'EOF' > seclorum/web/app.py
from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from seclorum.agents.master import MasterNode
import logging
import sys
import signal
import time

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app)
app.master_node = None
logging.basicConfig(filename='app.log', level=logging.DEBUG)

def get_master_node():
    global app
    if app.master_node is None:
        app.master_node = MasterNode()
        app.master_node.socketio = socketio
    return app.master_node

def run_app():
    master = get_master_node()
    master.start()
    socketio.emit("debug", {"message": "Server started"})
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    master = get_master_node()
    if not master.is_running():
        master.start()
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = str(int(time.time() * 1000))  # Unique timestamp-based ID
            master.process_task(task_id, task_description)
            return redirect(url_for("chat"))
    return render_template("chat.html", tasks=master.tasks)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/dashboard")
def dashboard():
    master = get_master_node()
    if not master.is_running():
        master.start()
    return render_template("dashboard.html", tasks=master.tasks)

@app.route("/delete_task/<task_id>", methods=["POST"])
def delete_task(task_id):
    master = get_master_node()
    if task_id in master.tasks:
        del master.tasks[task_id]
        master.save_tasks()
        return redirect(url_for("dashboard"))
    return redirect(url_for("dashboard"))

def shutdown_handler(signum, frame):
    master = get_master_node()
    master.stop()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        master = get_master_node()
        if master.is_running():
            master.stop()
            print("MasterNode stopped via CLI")
        else:
            print("MasterNode is not running")
    else:
        run_app()
