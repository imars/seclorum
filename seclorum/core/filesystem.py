# seclorum/core/filesystem.py
import git
from pathlib import Path
import subprocess
import os
from seclorum.utils.logger import LoggerMixin

class FileSystemManager(LoggerMixin):
    def __init__(self, repo_path: str = "."):
        self.name = "FileSystemManager"  # For LoggerMixin
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            raise ValueError(f"{self.repo_path} is not a Git repository")

    def commit_changes(self, message: str) -> bool:
        try:
            # Stage all changes
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True, capture_output=True, text=True)
            # Check if there’s anything to commit
            status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True)
            if status.stdout.strip():
                # Commit with message
                subprocess.run(["git", "commit", "-m", message], cwd=self.repo_path, check=True, capture_output=True, text=True)
                self.log_update(f"Committed changes: {message}")
            else:
                self.log_update(f"No changes to commit: {message}")
            return True
        except subprocess.CalledProcessError as e:
            self.log_update(f"Failed to commit changes: {e.output}")
            return False

    def save_file(self, filename: str, content: str):
        with open(self.path / filename, "w") as f:
            f.write(content)
        self.repo.index.add([filename])
        self.repo.index.commit(f"Update {filename}")

    def get_file(self, filename: str) -> str:
        with open(self.path / filename, "r") as f:
            return f.read()
