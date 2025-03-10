from pathlib import Path
from .checkpoint import CheckpointManager

class Bootstrap:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.checkpoint_manager = CheckpointManager(project_path)
        self.chat_log_path = self.project_path / "chat_log.txt"

    def generate_prompt(self) -> str:
        """Generate a prompt from the latest checkpoint and chat history."""
        latest_checkpoint = self.checkpoint_manager.get_latest_checkpoint()
        
        if not latest_checkpoint:
            return "No previous checkpoints found. Starting a new session."

        # Read recent chat history
        chat_history = ""
        if self.chat_log_path.exists():
            with open(self.chat_log_path, "r") as log_file:
                lines = log_file.readlines()
                # Take the last 10 lines or all if fewer, assuming each message is a line
                recent_lines = lines[-10:] if len(lines) > 10 else lines
                chat_history = "".join(recent_lines).strip()

        # Format the prompt
        prompt = (
            "Resuming development session for Seclorum:\n\n"
            f"Latest Checkpoint:\n"
            f"- Timestamp: {latest_checkpoint['timestamp']}\n"
            f"- Edited Files: {', '.join(latest_checkpoint['edited_files']) or 'None'}\n"
            f"- Chat URL: {latest_checkpoint['chat_url']}\n"
            f"- Checkpoint Hash: {latest_checkpoint['hash']}\n\n"
            "Recent Chat History:\n"
            f"{chat_history or 'No recent chat history available.'}\n\n"
            "Please assist me in continuing from where I left off."
        )

        return prompt
