from abc import ABC, abstractmethod
import json
import os
from seclorum.core.filesystem import FileSystemManager

class Agent(ABC):
    def __init__(self, name, repo_path="project"):
        self.name = name
        self.repo_path = repo_path
        self.tasks = {}
        self.fs_manager = FileSystemManager(repo_path)

    def log_update(self, message):
        with open("log.txt", "a") as f:
            f.write(f"{self.name}: {message}\n")

    def commit_changes(self, message):
        # Use FileSystemManager to commit changes
        self.fs_manager.save_file("changes.txt", f"{self.name}: {message}")
        self.log_update(f"Committed changes: {message}")

    def save_tasks(self):
        with open(f"{self.name}_tasks.json", "w") as f:
            json.dump(self.tasks, f)

    @abstractmethod
    def process_task(self, task_id, description):
        """Process a task with given ID and description."""
        pass

    @abstractmethod
    def start(self):
        """Start the agent's resources and processes."""
        pass

    @abstractmethod
    def stop(self):
        """Stop the agent's resources and processes."""
        pass

if __name__ == "__main__":
    # Abstract class, not instantiated directly
    pass
