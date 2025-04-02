# seclorum/agents/base.py
from abc import ABC, abstractmethod
import os
import logging
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory_manager import MemoryManager  # Updated import
from seclorum.models import Task, AgentMessage

logger = logging.getLogger("Agent")
logging.basicConfig(
    filename=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'log.txt')),
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    filemode='a'
)

class AbstractAgent(ABC):
    def __init__(self, name: str, session_id: str = "default_session", repo_path: str = "project"):
        self.name = name
        self.session_id = session_id
        self.repo_path = repo_path
        self.memory = MemoryManager(session_id)  # Updated to MemoryManager
        self.fs_manager = FileSystemManager(repo_path)
        self.logger = logging.getLogger(f"Agent_{name}")
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.handlers = [handler]
        self.logger.propagate = False
        self.logger.info(f"Initialized {self.name} with session {self.session_id}")

    def log_update(self, message: str):
        self.logger.info(f"{self.name}: {message}")
        self.memory.save(response=f"{self.name}: {message}")

    def commit_changes(self, message: str):
        self.fs_manager.save_file("changes.txt", f"{self.name}: {message}")
        self.log_update(f"Committed changes: {message}")

    def send_message(self, receiver: str, task: Task, content: str) -> str:
        message = AgentMessage(sender=self.name, receiver=receiver, task=task, content=content)
        return message.to_json()

    def receive_message(self, json_message: str) -> AgentMessage:
        return AgentMessage.from_json(json_message)

    @abstractmethod
    def process_task(self, task: Task) -> tuple[str, str]:
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass
