from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from seclorum.agents.master import MasterNode
import signal
import sys

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, message_queue='redis://')

master_node = None

def signal_handler(sig, frame):
    print("Shutting down...")
    if master_node:
        master_node.stop_ollama()
    sys.exit(0)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    global master_node
    if master_node is None:
        master_node = MasterNode()
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = len(master_node.tasks) + 1
            master_node.process_task(task_id, task_description)
            socketio.emit("task_update", {"task_id": task_id, "description": task_description, "status": "assigned", "result": ""})
            return redirect(url_for("chat"))
        message = "No task description provided."
    else:
        message = None
    master_node.check_sessions()
    return render_template("chat.html", message=message, tasks=master_node.tasks)

@app.route("/dashboard")
def dashboard():
    global master_node
    if master_node is None:
        master_node = MasterNode()
    master_node.check_sessions()
    active_sessions = master_node.active_sessions
    tasks = master_node.tasks
    print(f"DEBUG: tasks = {tasks}, active_sessions = {active_sessions}")
    return render_template("dashboard.html", active=active_sessions, tasks=tasks)

@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    global master_node
    if master_node is None:
        master_node = MasterNode()
    task_id_str = str(task_id)
    if task_id_str in master_node.tasks:
        del master_node.tasks[task_id_str]
        master_node.save_tasks()
        if task_id_str in master_node.active_sessions:
            proc = master_node.active_sessions[task_id_str]
            proc.terminate()
            del master_node.active_sessions[task_id_str]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Task not found"})

@socketio.on("connect")
def handle_connect(auth=None):
    global master_node
    if master_node is None:
        master_node = MasterNode()
    for task_id, task in master_node.tasks.items():
        result = task.get("result", "")
        emit("task_update", {"task_id": task["task_id"], "description": task["description"], "status": task["status"], "result": result})

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    try:
        socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
    finally:
        if master_node:
            master_node.stop_ollama()
