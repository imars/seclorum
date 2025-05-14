# seclorum/utils/logger.py
import json
import os
from datetime import datetime
import logging
from typing import List, Dict

# Define custom CONVERSATION logging level
CONVERSATION_LEVEL = 25
logging.addLevelName(CONVERSATION_LEVEL, "CONVERSATION")

def conversation(self, message, *args, **kwargs):
    if self.isEnabledFor(CONVERSATION_LEVEL):
        self._log(CONVERSATION_LEVEL, message, args, **kwargs)

logging.Logger.conversation = conversation

# Custom filter for CONVERSATION and ERROR+ logs
class ConversationOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == CONVERSATION_LEVEL or record.levelno >= logging.ERROR

# Clear root logger handlers to prevent interference
logging.getLogger('').handlers.clear()

# Configure global logger
logger = logging.getLogger("seclorum")
logger.handlers.clear()  # Clear existing handlers
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
default_level = os.getenv("LOG_LEVEL", "INFO").upper()
if default_level == "CONVERSATION":
    logger.setLevel(CONVERSATION_LEVEL)
    handler.setLevel(CONVERSATION_LEVEL)
    handler.addFilter(ConversationOnlyFilter())
else:
    logger_level = getattr(logging, default_level, logging.INFO)
    logger.setLevel(logger_level)
    handler.setLevel(logger_level)
logger.addHandler(handler)
logger.propagate = False  # Prevent propagation to root logger

class LoggerMixin:
    def __init__(self):
        self.logger = logging.getLogger(f"Agent_{self.name}")
        self.logs: List[Dict[str, str]] = []
        self.logger.handlers.clear()  # Clear existing handlers
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        default_level = os.getenv("LOG_LEVEL", "INFO").upper()
        if default_level == "CONVERSATION":
            self.logger.setLevel(CONVERSATION_LEVEL)
            handler.setLevel(CONVERSATION_LEVEL)
            handler.addFilter(ConversationOnlyFilter())
        else:
            logger_level = getattr(logging, default_level, logging.INFO)
            self.logger.setLevel(logger_level)
            handler.setLevel(logger_level)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False  # Prevent propagation to root logger

    def log_update(self, message: str):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "name": self.logger.name,
            "level": "INFO",
            "message": message
        }
        self.logs.append(log_entry)
        self.logger.info(message)

    def log_conversation(self, message: str):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "name": self.logger.name,
            "level": "CONVERSATION",
            "message": message
        }
        self.logs.append(log_entry)
        self.logger.conversation(message)

    def get_logs(self) -> List[Dict[str, str]]:
        return self.logs

class ConversationLogger:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.log_dir = "logs/conversations"
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"conversation_{chat_id}.json")
        self.logs = {"prompts": [], "responses": []}
        self.logger = logging.getLogger(f"Conversation_{chat_id}")
        self.logger.handlers.clear()  # Clear existing handlers
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        default_level = os.getenv("LOG_LEVEL", "INFO").upper()
        if default_level == "CONVERSATION":
            self.logger.setLevel(CONVERSATION_LEVEL)
            handler.setLevel(CONVERSATION_LEVEL)
            handler.addFilter(ConversationOnlyFilter())
        else:
            logger_level = getattr(logging, default_level, logging.INFO)
            self.logger.setLevel(logger_level)
            handler.setLevel(logger_level)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                self.logs = json.load(f)

    def log_prompt(self, prompt):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "text": prompt
        }
        self.logs["prompts"].append(entry)
        self.logger.conversation(f"Prompt: {prompt}")
        self._save()

    def log_response(self, response):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "text": response
        }
        self.logs["responses"].append(entry)
        self.logger.conversation(f"Response: {response}")
        self._save()

    def _save(self):
        with open(self.log_file, "w") as f:
            json.dump(self.logs, f, indent=2)

if __name__ == "__main__":
    os.environ["LOG_LEVEL"] = "CONVERSATION"
    logger = ConversationLogger("2025-03-11-1")
    logger.log_prompt("Test prompt")
    logger.log_response("Test response")
