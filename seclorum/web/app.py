from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from seclorum.agents.master import MasterNode
import logging

app = Flask(__name__, template_folder="templates")
app.master_node = None
socketio = SocketIO(app)
logging.basicConfig(filename='app.log', level=logging.DEBUG)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if app.master_node is None:
        app.master_node = MasterNode()
        app.master_node.start()
        logging.debug("MasterNode initialized and started")
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = len(app.master_node.tasks) + 1
            logging.debug(f"Assigning task {task_id}: {task_description}")
            app.master_node.process_task(task_id, task_description)
            socketio.emit("task_update", {"task_id": task_id, "description": task_description, "status": "assigned", "result": ""})
            logging.debug(f"Task {task_id} emitted to SocketIO")
            return redirect(url_for("chat"))
    return render_template("chat.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/dashboard")
def dashboard():
    if app.master_node is None:
        app.master_node = MasterNode()
        app.master_node.start()
        logging.debug("MasterNode initialized for dashboard")
    logging.debug(f"Rendering dashboard with tasks: {app.master_node.tasks}")
    return render_template("dashboard.html", tasks=app.master_node.tasks)

@app.route("/delete_task/<task_id>", methods=["POST"])
def delete_task(task_id):
    if app.master_node:
        logging.debug(f"Attempting to delete task {task_id}. Current tasks: {app.master_node.tasks}")
        if task_id in app.master_node.tasks:
            del app.master_node.tasks[task_id]
            app.master_node.save_tasks()
            logging.debug(f"Deleted task {task_id}")
            return redirect(url_for("dashboard"))
        logging.debug(f"Task {task_id} not found for deletion")
    else:
        logging.debug("MasterNode not initialized for delete")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
