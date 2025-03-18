import os
from flask import session
import logging
from seclorum.agents.master import MasterNode
import uuid
import threading

logger = logging.getLogger("Seclorum")
log_file = os.getenv("SECLORUM_LOG_FILE", "app.log")
handler = logging.FileHandler(log_file, mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def get_master_node(app, socketio):
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
