import os
from flask import Flask
from flask_socketio import SocketIO
from seclorum.web.utils import logger, get_master_node, quick_llm, deepseek_r1_8b, assess_complexity, get_agent_response

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "secret_key_for_development")
socketio = SocketIO(app, cors_allowed_origins="*")

def register_blueprints(app, socketio):
    from seclorum.web.routes.chat import chat_bp, set_socketio
    from seclorum.web.routes.dashboard import dashboard_bp
    from seclorum.web.routes.settings import settings_bp
    from seclorum.web.routes.tasks import tasks_bp
    from seclorum.web.routes.focus_chat import focus_chat_bp

    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(focus_chat_bp)

    # Set socketio for chat_bp
    set_socketio(socketio)

def run_app():
    logger.info("Starting Flask app")
    register_blueprints(app, socketio)
    socketio.run(app, host="127.0.0.1", port=5000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    run_app()
