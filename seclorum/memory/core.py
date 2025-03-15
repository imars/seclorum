import json
import os
from datetime import datetime

class ConversationMemory:
    """Manage conversation logs for cross-session memory."""
    def __init__(self, session_id, log_dir="logs/conversations"):
        self.session_id = session_id
        self.log_file = os.path.join(log_dir, f"conversation_{session_id}.json")
        self.log = self._load_log()

    def _load_log(self):
        """Load or initialize the conversation log."""
        if not os.path.exists(self.log_file):
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            default_log = {"prompts": [], "responses": [], "sessions": []}
            with open(self.log_file, "w") as f:
                json.dump(default_log, f, indent=4)
            return default_log
        with open(self.log_file, "r") as f:
            return json.load(f)

    def save(self, prompt=None, response=None, session_id=None):
        """Append a prompt, response, or session to the log."""
        timestamp = datetime.now().isoformat()
        if prompt:
            self.log["prompts"].append({"timestamp": timestamp, "text": prompt})
        if response:
            self.log["responses"].append({"timestamp": timestamp, "text": response})
        if session_id and session_id not in [s["id"] for s in self.log["sessions"]]:
            self.log["sessions"].append({"timestamp": timestamp, "id": session_id})
        with open(self.log_file, "w") as f:
            json.dump(self.log, f, indent=4)

    def get_summary(self, limit=5):
        """Return a formatted summary of recent conversation items."""
        prompts = self.log["prompts"]
        responses = self.log["responses"]
        sessions = self.log["sessions"]
        recent_prompts = prompts[-limit:] if len(prompts) > limit else prompts
        recent_responses = responses[-limit:] if len(responses) > limit else responses
        recent_sessions = sessions[-limit:] if len(sessions) > limit else sessions
        
        summary = f"* Conversation: {len(prompts)} prompts, {len(responses)} responses, {len(sessions)} sessions\n"
        summary += "Recent Sessions:\n"
        for s in recent_sessions:
            summary += f"* {s['timestamp']}: Session {s['id']}\n"
        summary += "Recent Prompts:\n"
        for p in recent_prompts:
            summary += f"* {p['timestamp']}: {p['text']}\n"
        summary += "Recent Responses:\n"
        for r in recent_responses:
            summary += f"* {r['timestamp']}: {r['text']}\n"
        return summary.rstrip()

if __name__ == "__main__":
    mem = ConversationMemory("test_session")
    mem.save(prompt="Hello, agent!")
    mem.save(response="Hi there!")
    mem.save(session_id="test_session")
    print(mem.get_summary())
