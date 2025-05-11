# seclorum/core/filesystem.py
import git
import os
import subprocess
from pathlib import Path
from typing import Dict, Set
from seclorum.utils.logger import LoggerMixin
from functools import lru_cache
import time

class FileSystemManager(LoggerMixin):
    _instances: Dict[str, 'FileSystemManager'] = {}

    @classmethod
    def get_instance(cls, repo_path: str = ".", require_git: bool = False) -> 'FileSystemManager':
        """Singleton pattern to ensure one instance per repo_path."""
        repo_path = os.path.abspath(repo_path)
        if repo_path not in cls._instances:
            cls._instances[repo_path] = cls(repo_path, require_git)
        return cls._instances[repo_path]

    def __init__(self, repo_path: str = ".", require_git: bool = False):
        if repo_path in self._instances:
            raise ValueError("Use get_instance to access FileSystemManager")
        self.name = "FileSystemManager"
        super().__init__()
        self.repo_path = os.path.abspath(repo_path)
        self.is_git_repo = os.path.exists(os.path.join(self.repo_path, ".git"))
        if require_git and not self.is_git_repo:
            raise ValueError(f"{self.repo_path} is not a Git repository")
        self.log_update(f"Initialized FileSystemManager at {self.repo_path}, is_git_repo: {self.is_git_repo}")
        self._staged_files: Set[str] = set()  # Track staged files for batch commits
        self._file_cache: Dict[str, str] = {}  # In-memory file cache

    def commit_changes(self, message: str, max_retries: int = 3, retry_delay: float = 1.0) -> bool:
        """Commit all staged changes in one operation with retry logic."""
        if not self.is_git_repo:
            self.log_update(f"Skipping commit in non-Git directory: {self.repo_path}")
            return False
        if not self._staged_files:
            self.log_update(f"No files staged for commit: {message}")
            return True

        for attempt in range(1, max_retries + 1):
            try:
                subprocess.run(
                    ["git", "add"] + list(self._staged_files),
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                subprocess.run(
                    ["git", "commit", "-m", message],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                self.log_update(f"Committed changes: {message}")
                self._staged_files.clear()
                return True
            except subprocess.CalledProcessError as e:
                self.log_update(f"Attempt {attempt}/{max_retries} failed to commit changes: {e.stderr}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                continue
            except Exception as e:
                self.log_update(f"Unexpected error during commit: {str(e)}")
                return False
        self.log_update(f"Failed to save file {filename}: {str(e)}")
        return False

    def save_file(self, filename: str, content: str, validate_filename: bool = True) -> bool:
        """Save a file and stage it for commit."""
        try:
            if validate_filename:
                self._validate_filename(filename)
            file_path = os.path.join(self.repo_path, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            self._file_cache[filename] = content
            if self.is_git_repo:
                subprocess.run(
                    ["git", "add", filename],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                    text=True
                )
                self._staged_files.add(filename)
            self.log_update(f"Saved and staged file: {filename}")
            return True
        except (OSError, subprocess.CalledProcessError, ValueError) as e:
            self.log_update(f"Failed to save file {filename}: {str(e)}")
            return False

    @lru_cache(maxsize=100)
    def get_file(self, filename: str) -> str:
        """Read a file, using cache if available."""
        try:
            self._validate_filename(filename)
            if filename in self._file_cache:
                self.log_update(f"Retrieved file from cache: {filename}")
                return self._file_cache[filename]
            file_path = os.path.join(self.repo_path, filename)
            with open(file_path, "r") as f:
                content = f.read()
            self._file_cache[filename] = content
            self.log_update(f"Read file: {filename}")
            return content
        except FileNotFoundError:
            self.log_update(f"File not found: {filename}")
            raise
        except OSError as e:
            self.log_update(f"Error reading file {filename}: {str(e)}")
            raise

    @classmethod
    def clear_all_caches(cls):
        """Clear caches for all instances."""
        for instance in cls._instances.values():
            instance.clear_cache()

    def _validate_filename(self, filename: str) -> None:
        """Validate that the filename is safe and within the repository."""
        # Early check for '..' components
        self.log_update(f"Checking for parent directory references in {filename}")
        if '..' in filename.split(os.sep):
            self.log_update(f"Filename {filename} rejected due to parent directory references")
            raise ValueError(f"Filename {filename} attempts to access outside repository")

        repo_path = Path(self.repo_path).resolve()
        file_path = Path(os.path.join(self.repo_path, filename)).resolve(strict=False)
        self.log_update(f"Validating filename: {filename}, resolved to {file_path}, repo_path: {repo_path}")

        if not str(file_path).startswith(str(repo_path) + os.sep):
            self.log_update(f"Filename {filename} rejected: resolved path outside repository")
            raise ValueError(f"Filename {filename} attempts to access outside repository")

        if file_path.is_symlink():
            self.log_update(f"Filename {filename} rejected: symbolic link detected")
            raise ValueError(f"Filename {filename} is a symbolic link, which is not allowed")

        self.log_update(f"Checking for invalid characters in {filename}")
        if any(c in filename for c in '<>|*?'):
            self.log_update(f"Filename {filename} rejected: contains invalid characters")
            raise ValueError(f"Filename {filename} contains invalid characters")

    def clear_cache(self):
        """Clear the file cache."""
        self._file_cache.clear()
        self.get_file.cache_clear()
        self.log_update("Cleared file cache")

    def get_staged_files(self) -> Set[str]:
        """Return the set of currently staged files."""
        return self._staged_files.copy()
