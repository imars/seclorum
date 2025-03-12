from flask import Flask, request, render_template, redirect, url_for
from seclorum.agents.master import MasterNode

app = Flask(__name__)

def get_master_node():
    master = MasterNode()  # Fresh instance per request
    master.check_sessions()  # Update statuses
    return master

@app.route("/chat", methods=["GET", "POST"])
def chat():
    master_node = get_master_node()
    if request.method == "POST" and "task" in request.form:
        task_description = request.form["task"]
        if task_description:
            task_id = len(master_node.tasks) + 1
            master_node.process_task(task_id, task_description)
            return redirect(url_for("chat"))  # Redirect to GET after POST
        message = "No task description provided."
    else:
        message = None
    
    return render_template("chat.html", message=message, tasks=master_node.tasks)

if __name__ == "__main__":
    app.run(debug=True)
