# seclorum/core/filesystem.py
import git
import os
import subprocess
from pathlib import Path
from seclorum.utils.logger import LoggerMixin

class FileSystemManager(LoggerMixin):
    def __init__(self, repo_path: str = ".", require_git: bool = False):
        self.name = "FileSystemManager"
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        self.is_git_repo = os.path.exists(os.path.join(self.repo_path, ".git"))
        if require_git and not self.is_git_repo:
            raise ValueError(f"{self.repo_path} is not a Git repository")
        self.log_update(f"Initialized FileSystemManager at {self.repo_path}, is_git_repo: {self.is_git_repo}")

    def commit_changes(self, message: str) -> bool:
        if not self.is_git_repo:
            self.log_update(f"Skipping commit in non-Git directory: {self.repo_path}")
            return False
        try:
            subprocess.run(["git", "add", "."], cwd=self.repo_path, check=True, capture_output=True, text=True)
            status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo_path, capture_output=True, text=True)
            if status.stdout.strip():
                subprocess.run(["git", "commit", "-m", message], cwd=self.repo_path, check=True, capture_output=True, text=True)
                self.log_update(f"Committed changes: {message}")
            else:
                self.log_update(f"No changes to commit: {message}")
            return True
        except subprocess.CalledProcessError as e:
            self.log_update(f"Failed to commit changes: {e.output}")
            return False

    def save_file(self, filename: str, content: str):
        file_path = os.path.join(self.repo_path, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        if self.is_git_repo:
            subprocess.run(["git", "add", filename], cwd=self.repo_path, check=True, capture_output=True, text=True)
            subprocess.run(["git", "commit", "-m", f"Update {filename}"], cwd=self.repo_path, check=True, capture_output=True, text=True)
        self.log_update(f"Saved file: {filename}")

    def get_file(self, filename: str) -> str:
        file_path = os.path.join(self.repo_path, filename)
        with open(file_path, "r") as f:
            return f.read()
