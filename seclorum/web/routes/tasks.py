from flask import Blueprint, redirect, url_for, current_app
from seclorum.web.utils import get_master_node
from seclorum.web.app import socketio

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/delete_task/<task_id>', methods=['POST'])
def delete_task(task_id):
    master = get_master_node(current_app, socketio)
    if task_id in master.tasks:
        del master.tasks[task_id]
        master.save_tasks()
    return redirect(url_for('dashboard.dashboard'))
