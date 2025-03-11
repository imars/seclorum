import json
import os
from datetime import datetime

class ConversationLogger:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.log_dir = "logs/conversations"
        os.makedirs(self.log_dir, exist_ok=True)  # Create directories if they don't exist
        self.log_file = os.path.join(self.log_dir, f"conversation_{chat_id}.json")
        self.logs = {"prompts": [], "responses": []}
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                self.logs = json.load(f)

    def log_prompt(self, prompt):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "text": prompt
        }
        self.logs["prompts"].append(entry)
        self._save()

    def log_response(self, response):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "text": response
        }
        self.logs["responses"].append(entry)
        self._save()

    def _save(self):
        with open(self.log_file, "w") as f:
            json.dump(self.logs, f, indent=2)

    def get_conversation(self):
        return self.logs

if __name__ == "__main__":
    logger = ConversationLogger("2025-03-11-1")
    logger.log_prompt("Test prompt")
    logger.log_response("Test response")
