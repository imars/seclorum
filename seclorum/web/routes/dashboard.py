from flask import Blueprint, render_template, current_app
from seclorum.web.utils import get_master_node
from seclorum.web.app import socketio

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    master = get_master_node(current_app, socketio)
    return render_template('dashboard.html', tasks=master.tasks)
