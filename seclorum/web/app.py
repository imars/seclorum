from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO, emit
from seclorum.agents.master import MasterNode

app = Flask(__name__, template_folder="templates")
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app)
master_node = None

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

@socketio.on("connect")
def handle_connect():
    global master_node
    if master_node is None:
        master_node = MasterNode()
    for task_id, task in master_node.tasks.items():
        emit("task_update", {"task_id": task["task_id"], "description": task["description"], "status": task["status"], "result": task["result"]})

if __name__ == "__main__":
    try:
        socketio.run(app, debug=True)
    finally:
        if master_node:
            master_node.stop_ollama()
