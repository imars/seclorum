from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from seclorum.agents.master import MasterNode

app = Flask(__name__, template_folder="templates")
app.master_node = None
socketio = SocketIO(app)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if app.master_node is None:
        app.master_node = MasterNode()
        app.master_node.start()
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = len(app.master_node.tasks) + 1
            app.master_node.process_task(task_id, task_description)
            socketio.emit("task_update", {"task_id": task_id, "description": task_description, "status": "assigned", "result": ""})
            return redirect(url_for("chat"))
    return render_template("chat.html")

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/dashboard")
def dashboard():
    if app.master_node is None:
        return "MasterNode not initialized", 500
    return render_template("dashboard.html")

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
