from flask import Blueprint, render_template, request, current_app
from seclorum.web.utils import logger, get_agent_response

focus_chat_bp = Blueprint('focus_chat', __name__)

@focus_chat_bp.route('/focus_chat', methods=['GET', 'POST'])
def focus_chat():
    master = current_app.config['MASTER_NODE']
    task_id = request.args.get('task_id', 'master')
    
    if request.method == 'POST':
        input_text = request.form.get('input', '').strip()
        if input_text:
            logger.info(f"Received POST input for task_id {task_id}: '{input_text}'")
            response = get_agent_response(master, input_text)
            logger.info(f"Generated response for task_id {task_id}: '{response}'")
            master.memory.save(prompt=input_text, response=response, task_id=task_id if task_id != 'master' else None)
            if master.socketio:
                event_data = {'prompt': input_text, 'response': response, 'task_id': task_id}
                master.socketio.emit('chat_update', event_data)  # No namespace
                logger.info(f"Emitted chat_update event: {event_data}")
            else:
                logger.error("SocketIO not initialized, chat_update not emitted")
            return '', 204
    
    conversation_history = master.memory.load_conversation_history(task_id=task_id) or ""
    agent_name = 'MasterNode' if task_id == 'master' else f'Agent {task_id}'
    logger.info(f"Rendering focus_chat for {agent_name}, history length: {len(conversation_history.splitlines())}")
    return render_template('focus_chat.html', agent_name=agent_name, task_id=task_id, conversation_history=conversation_history)
