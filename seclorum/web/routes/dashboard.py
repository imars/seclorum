from flask import Blueprint, render_template, current_app, request
from seclorum.web.utils import get_master_node
from seclorum.web.app import socketio

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    master = get_master_node(current_app, socketio)
    mode = request.args.get('mode', 'user')  # Default to 'user' if not specified
    task_id = request.args.get('task_id', 'master')  # Default to 'master'
    return render_template('dashboard.html', tasks=master.tasks, mode=mode, task_id=task_id)
