import os
from flask import Flask
from flask_socketio import SocketIO
from seclorum.web.routes.chat import chat_bp, set_socketio
from seclorum.web.routes.focus_chat import focus_chat_bp
from seclorum.web.utils import logger
from seclorum.agents.master import MasterNode

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize MasterNode and set its SocketIO
master_node = MasterNode(session_id="default_session")
master_node.socketio = socketio
master_node.start()

# Set SocketIO for chat_bp
set_socketio(socketio)

# Register blueprints
app.register_blueprint(chat_bp)
app.register_blueprint(focus_chat_bp)

# Store master_node in app config
app.config['MASTER_NODE'] = master_node

logger.info("Flask app initialized with SocketIO and MasterNode")

if __name__ == '__main__':
    logger.info("Starting Flask app with SocketIO on 127.0.0.1:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, use_reloader=False)
