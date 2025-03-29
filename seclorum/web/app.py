import os
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_socketio import SocketIO
from seclorum.web.routes.chat import chat_bp, set_socketio
from seclorum.web.routes.focus_chat import focus_chat_bp
from seclorum.web.utils import logger
from seclorum.agents.master import MasterNode

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Serve favicon explicitly
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico')

# Initialize MasterNode and set its SocketIO
master_node = MasterNode(session_id="default_session")
master_node.socketio = socketio
master_node.start()

# Set SocketIO for chat_bp
set_socketio(socketio)

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(focus_chat_bp)

# Store master_node in app config
app.config['MASTER_NODE'] = master_node

# Add Dashboard and Settings routes
@app.route('/dashboard')
def dashboard():
    logger.info("Rendering dashboard page")
    master = app.config['MASTER_NODE']
    tasks = master.tasks
    mode = request.args.get('mode', 'design')
    task_id = request.args.get('task_id', 'master')
    return render_template('dashboard.html', tasks=tasks, mode=mode, task_id=task_id)

@app.route('/settings')
def settings():
    logger.info("Rendering settings page")
    mode = request.args.get('mode', 'design')
    task_id = request.args.get('task_id', 'master')
    return render_template('settings.html', mode=mode, selectedAgent=task_id)

@app.route('/delete_task/<task_id>', methods=['POST'])
def delete_task(task_id):
    logger.info(f"Deleting task {task_id}")
    master = app.config['MASTER_NODE']
    if task_id in master.tasks:
        del master.tasks[task_id]
        master.save_tasks()
        logger.info(f"Task {task_id} deleted")
    return redirect(url_for('dashboard', mode=request.args.get('mode', 'design'), task_id=request.args.get('task_id', 'master')))

logger.info("Flask app initialized with SocketIO and MasterNode")

if __name__ == '__main__':
    logger.info("Starting Flask app with SocketIO on 127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, use_reloader=False)
