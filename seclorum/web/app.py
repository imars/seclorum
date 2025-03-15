import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO
import logging
from seclorum.agents.master import MasterNode
import uuid
import time

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret_key_for_development")
socketio = SocketIO(app, cors_allowed_origins="*")

logger = logging.getLogger("Seclorum")
log_file = os.getenv("SECLORUM_LOG_FILE", "app.log")
handler = logging.FileHandler(log_file, mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Simulated local LLMs
def quick_llm(prompt, context=""):
    if "morning" in prompt.lower():
        return f"Good morning! How’s your day? (Memory: {context})"
    elif "what's" in prompt.lower():
        return f"Code and coffee here. You? (Memory: {context})"
    else:
        return None

def deepseek_r1_8b(prompt, context=""):
    if "haiku" in prompt.lower():
        return "Soft winds whisper low\nBlossoms fade in twilight’s glow\nTime drifts ever on"
    elif "analyze" in prompt.lower():
        return f"Analyzing with memory: {context}"
    else:
        return f"DeepSeek-R1:8b here. Query: {prompt}. Memory: {context}"

def assess_complexity(prompt, memory_context):
    words = prompt.split()
    complexity_score = len(words)
    has_context = any(m["similarity"] > 0.8 for m in memory_context)
    if "haiku" in prompt.lower() or "analyze" in prompt.lower() or complexity_score > 5 or has_context:
        return "complex"
    return "simple"

def get_agent_response(master, prompt):
    logger.info(f"Assessing prompt: {prompt}")
    # Query vector memory
    memory_context = master.memory.query_memory(prompt)
    context = " ".join([m["text"] for m in memory_context]) if memory_context else "No relevant history"
    complexity = assess_complexity(prompt, memory_context)
    logger.info(f"Complexity: {complexity}, Memory context: {context[:50]}...")
    if complexity == "simple":
        response = quick_llm(prompt, context)
        if response:
            logger.info("Quick LLM handled prompt")
            return response
    logger.info("Escalating to DeepSeek-R1:8b")
    return deepseek_r1_8b(prompt, context)

def get_master_node():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']
    if not hasattr(app, 'master_node') or app.master_node.session_id != session_id:
        logger.info(f"Initializing MasterNode with session {session_id}")
        app.master_node = MasterNode(session_id=session_id)
        app.master_node.socketio = socketio
        app.master_node.start()
        logger.info(f"MasterNode started, emitting debug")
        socketio.emit('debug', {'msg': f"MasterNode started with session {session_id}"}, namespace='/')
    return app.master_node

@app.route('/')
def index():
    return redirect(url_for('chat'))

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    logger.info("Handling /chat request")
    master = get_master_node()
    mode = request.args.get('mode', 'task')
    if request.method == 'POST':
        input_text = request.form.get('input', '').strip()
        logger.info(f"Received POST input: {input_text} in mode {mode}")
        if not input_text:
            logger.warning("Empty input received")
            return redirect(url_for('chat', mode=mode))
        if mode == 'task' or "haiku" in input_text.lower():
            task_id = str(int(time.time() * 1000))
            logger.info(f"Processing task {task_id}: {input_text}")
            master.process_task(task_id, input_text)
            return redirect(url_for('chat', mode=mode))
        else:
            logger.info(f"Saving agent message: {input_text}")
            response = get_agent_response(master, input_text)
            master.memory.save(prompt=input_text, response=response)
            socketio.emit('chat_update', {'prompt': input_text, 'response': response}, namespace='/')
            logger.info(f"Emitted chat_update: {{'prompt': '{input_text}', 'response': '{response}'}}")
            return '', 204
    conversation_history = master.memory.load_conversation_history()
    logger.info(f"Rendering chat with history: {conversation_history[:50]}...")
    return render_template('chat.html', mode=mode, conversation_history=conversation_history, agents=master.tasks, tasks=master.tasks)

@app.route('/dashboard')
def dashboard():
    master = get_master_node()
    return render_template('dashboard.html', tasks=master.tasks)

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/delete_task/<task_id>', methods=['POST'])
def delete_task(task_id):
    master = get_master_node()
    if task_id in master.tasks:
        del master.tasks[task_id]
        master.save_tasks()
    return redirect(url_for('dashboard'))

def run_app():
    logger.info("Starting Flask app")
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    run_app()
