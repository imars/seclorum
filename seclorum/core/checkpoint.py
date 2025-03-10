import json
import hashlib
from datetime import datetime
from pathlib import Path
import git
from typing import List, Dict, Optional

class CheckpointManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.repo = git.Repo(self.project_path)
        self.chat_log_path = self.project_path / "chat_log.txt"
        self.checkpoint_path = self.project_path / "checkpoints.jsonl"

    def append_chat_history(self, chat_messages: List[Dict[str, str]]) -> None:
        """Append recent chat history to the chat log."""
        with open(self.chat_log_path, "a") as log_file:
            for msg in chat_messages:
                log_file.write(f"{msg.get('role', 'unknown')}: {msg.get('content', '')}\n")
            log_file.write("-" * 50 + "\n")

    def create_checkpoint(self, chat_url: str, chat_messages: List[Dict[str, str]], edited_files: List[str]) -> str:
        """Create a new checkpoint and commit it to Git."""
        # Generate a hash of the chat URL for indexing
        checkpoint_hash = hashlib.sha256(chat_url.encode()).hexdigest()

        # Create checkpoint data
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "edited_files": edited_files,
            "chat_url": chat_url,
            "hash": checkpoint_hash
        }

        # Append chat history
        self.append_chat_history(chat_messages)

        # Append checkpoint to JSONL file
        with open(self.checkpoint_path, "a") as cp_file:
            cp_file.write(json.dumps(checkpoint) + "\n")

        # Git commit
        self.repo.index.add([str(self.chat_log_path), str(self.checkpoint_path)])
        self.repo.index.commit(f"Checkpoint: {checkpoint_hash}")

        return checkpoint_hash

    def get_latest_checkpoint(self) -> Optional[Dict]:
        """Retrieve the latest checkpoint from the JSONL file."""
        if not self.checkpoint_path.exists():
            return None
        
        with open(self.checkpoint_path, "r") as cp_file:
            lines = cp_file.readlines()
            if lines:
                return json.loads(lines[-1].strip())
        return None
