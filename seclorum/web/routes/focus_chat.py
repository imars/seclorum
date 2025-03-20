from flask import Blueprint, render_template, request, current_app
from seclorum.web.utils import get_master_node, get_agent_response
from seclorum.web.app import socketio

focus_chat_bp = Blueprint('focus_chat', __name__)

@focus_chat_bp.route('/focus_chat', methods=['GET', 'POST'])
def focus_chat():
    master = get_master_node(current_app, socketio)
    task_id = request.args.get('task_id', 'master')  # Default to 'master'
    
    if request.method == 'POST':
        input_text = request.form.get('input', '').strip()
        if input_text:
            response = get_agent_response(master, input_text)
            master.memory.save(prompt=input_text, response=response, task_id=task_id if task_id != 'master' else None)
            if socketio:
                socketio.emit('chat_update', {'prompt': input_text, 'response': response, 'task_id': task_id}, namespace='/')
            return '', 204  # No content response to stay on page
    
    # Load conversation history for the selected agent
    conversation_history = master.memory.load_conversation_history(task_id=task_id) or ""
    agent_name = 'MasterNode' if task_id == 'master' else f'Agent {task_id}'
    
    return render_template('focus_chat.html', agent_name=agent_name, task_id=task_id, conversation_history=conversation_history)
