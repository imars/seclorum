from flask import Flask, request, render_template, redirect, url_for
from flask_socketio import SocketIO
from seclorum.agents.master import MasterNode
import logging
import sys
import signal
import time
import uuid

app = Flask(__name__, template_folder="templates")
socketio = SocketIO(app)
app.master_node = None
logging.basicConfig(filename='app.log', level=logging.DEBUG)
logger = logging.getLogger("App")

def get_master_node(session_id=None):
    global app
    if app.master_node is None:
        session_id = session_id or str(uuid.uuid4())
        logger.info(f"Initializing MasterNode with session {session_id}")
        app.master_node = MasterNode(session_id=session_id)
        app.master_node.socketio = socketio
    return app.master_node

def run_app():
    logger.info("Starting Flask app")
    master = get_master_node()
    master.start()
    logger.info("MasterNode started, emitting debug")
    socketio.emit("debug", {"message": "Server started"}, namespace='/')
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, use_reloader=False)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    logger.info("Handling /chat request")
    master = get_master_node()
    if not master.is_running():
        logger.info("MasterNode not running, starting")
        master.start()
    master.check_stuck_tasks()
    mode = request.args.get("mode", "task")  # Default to task mode
    if request.method == "POST" and "input" in request.form:
        user_input = request.form["input"]
        if user_input:
            task_id = str(int(time.time() * 1000))
            if mode == "task":
                logger.info(f"Processing task {task_id}: {user_input}")
                master.process_task(task_id, user_input)
            else:  # agent mode
                logger.info(f"Sending prompt to agent: {user_input}")
                master.memory.save(prompt=user_input)
                # TODO: Implement agent response logic
                master.memory.save(response=f"Echo from agent: {user_input}")
            return redirect(url_for("chat", mode=mode))
    if master.redis_available:
        master.tasks = master.load_tasks() or {}
    agents = {task_id: {"id": task_id, "output": task.get("result", "Pending...")} for task_id, task in master.tasks.items()}
    return render_template("chat.html", 
                         tasks=master.tasks, 
                         agents=agents,
                         conversation_history=master.memory.get_summary(),
                         mode=mode)

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route("/dashboard")
def dashboard():
    master = get_master_node()
    if not master.is_running():
        master.start()
    if master.redis_available:
        master.tasks = master.load_tasks() or {}
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
    logger.info("Received shutdown signal")
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
            logger.info("MasterNode stopped via CLI")
        else:
            logger.info("MasterNode is not running")
    else:
        run_app()
