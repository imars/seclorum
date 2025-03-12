from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app, message_queue='redis://')

# master_node will be set by manage_seclorum.py
app.master_node = None

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if app.master_node is None:
        return "MasterNode not initialized", 500
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = len(app.master_node.tasks) + 1
            app.master_node.process_task(task_id, task_description)
            socketio.emit("task_update", {"task_id": task_id, "description": task_description, "status": "assigned", "result": ""})
            return redirect(url_for("chat"))
        message = "No task description provided."
    else:
        message = None
    app.master_node.check_sessions()
    return render_template("chat.html", message=message, tasks=app.master_node.tasks)

@app.route("/dashboard")
def dashboard():
    if app.master_node is None:
        return "MasterNode not initialized", 500
    app.master_node.check_sessions()
    active_sessions = app.master_node.active_sessions
    tasks = app.master_node.tasks
    print(f"DEBUG: tasks = {tasks}, active_sessions = {active_sessions}")
    return render_template("dashboard.html", active=active_sessions, tasks=tasks)

@app.route("/delete_task/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if app.master_node is None:
        return jsonify({"success": False, "error": "MasterNode not initialized"}), 500
    task_id_str = str(task_id)
    if task_id_str in app.master_node.tasks:
        del app.master_node.tasks[task_id_str]
        app.master_node.save_tasks()
        if task_id_str in app.master_node.active_sessions:
            proc = app.master_node.active_sessions[task_id_str]
            proc.terminate()
            del app.master_node.active_sessions[task_id_str]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Task not found"})

@socketio.on("connect")
def handle_connect(auth=None):
    if app.master_node is None:
        return
    for task_id, task in app.master_node.tasks.items():
        result = task.get("result", "")
        emit("task_update", {"task_id": task["task_id"], "description": task["description"], "status": task["status"], "result": result})

if __name__ == "__main__":
    from seclorum.agents.master import MasterNode
    app.master_node = MasterNode()
    app.master_node.start()
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
