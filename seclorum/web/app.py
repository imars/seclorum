from flask import Flask, render_template, request
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.master import MasterNode

app = Flask(__name__)
fs_manager = FileSystemManager("./project")
master_node = MasterNode()

@app.route("/")
def index():
    files = [f.name for f in fs_manager.path.iterdir() if f.is_file()]
    return render_template("index.html", files=files)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        task_description = request.form.get("task")
        if task_description:
            task_id = len(master_node.tasks) + 1  # Simple ID generation
            master_node.process_task(task_id, task_description)
            return render_template("chat.html", message=f"Task {task_id} submitted!")
    return render_template("chat.html", message=None)
