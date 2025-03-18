from flask import Blueprint, render_template, request, redirect, url_for, current_app
from seclorum.web.utils import logger, get_master_node, get_agent_response
import time
import threading

chat_bp = Blueprint('chat', __name__)

# SocketIO will be set after registration
socketio = None

def set_socketio(sio):
    global socketio
    socketio = sio

@chat_bp.route('/')
def index():
    return redirect(url_for('chat.chat'))

@chat_bp.route('/chat', methods=['GET', 'POST'])
def chat():
    logger.info("Handling /chat request")
    master = get_master_node(current_app, socketio)
    mode = request.args.get('mode', 'task')
    task_id = request.args.get('task_id', 'master')  # Default to 'master' if not specified
    logger.info(f"Selected task_id: {task_id}")
    if request.method == 'POST':
        input_text = request.form.get('input', '').strip()
        logger.info(f"Received POST input: {input_text} in mode {mode} with task_id {task_id}")
        if not input_text:
            logger.warning("Empty input received")
            return redirect(url_for('chat.chat', mode=mode, task_id=task_id))
        if mode == 'task' or "haiku" in input_text.lower():
            task_id = str(int(time.time() * 1000))
            logger.info(f"Processing task {task_id}: {input_text}")
            master.process_task(task_id, input_text)
            return redirect(url_for('chat.chat', mode=mode, task_id=task_id))
        else:
            logger.info(f"Saving agent message: {input_text} for task_id {task_id}")
            response = get_agent_response(master, input_text)
            master.memory.save(prompt=input_text, response=response, task_id=task_id if task_id != 'master' else None)
            logger.info(f"Queue size after save: {len(master.memory.embedding_queue)}")
            if master.memory.embedding_queue and (not master.embedding_thread or not master.embedding_thread.is_alive()):
                logger.info("Starting new embedding thread")
                master.embedding_thread = threading.Thread(target=master.process_embedding_queue)
                master.embedding_thread.start()
            if socketio:
                socketio.emit('chat_update', {'prompt': input_text, 'response': response, 'task_id': task_id}, namespace='/')
                logger.info(f"Emitted chat_update: {{'prompt': '{input_text}', 'response': '{response}', 'task_id': '{task_id}'}}")
            return '', 204
    conversation_history = master.memory.load_conversation_history() or ""
    agents = master.tasks if master.tasks is not None else {}
    agent_histories = {}
    for tid in list(agents.keys()) + ['master']:
        agent_histories[tid] = master.memory.load_conversation_history(task_id=tid)
    logger.info(f"Rendering chat with history: {conversation_history[:50]}..., agents: {agents}, selected_task_id: {task_id}")
    return render_template('chat.html', mode=mode, conversation_history=conversation_history, agents=agents, tasks=agents, agent_histories=agent_histories, selected_task_id=task_id)
