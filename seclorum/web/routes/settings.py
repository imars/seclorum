from flask import Blueprint, render_template, request

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings')
def settings():
    mode = request.args.get('mode', 'user')  # Default to 'user'
    task_id = request.args.get('task_id', 'master')  # Default to 'master'
    return render_template('settings.html', mode=mode, task_id=task_id)
