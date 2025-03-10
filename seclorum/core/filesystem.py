import git
from pathlib import Path

class FileSystemManager:
    def __init__(self, project_path: str):
        self.path = Path(project_path)
        self.repo = git.Repo.init(self.path)

    def save_file(self, filename: str, content: str):
        with open(self.path / filename, "w") as f:
            f.write(content)
        self.repo.index.add([filename])
        self.repo.index.commit(f"Update {filename}")

    def get_file(self, filename: str) -> str:
        with open(self.path / filename, "r") as f:
            return f.read()
