# seclorum/agents/base.py
from abc import ABC, abstractmethod
import os
import logging
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory_manager import MemoryManager
from seclorum.models import Task, AgentMessage
from typing import Dict, List, Optional
from collections import defaultdict

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
        self.memory = MemoryManager(session_id)
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


class AbstractAggregate(AbstractAgent):
    def __init__(self, name: str, session_id: str = "default_session", repo_path: str = "project"):
        super().__init__(name, session_id, repo_path)
        self.agents: Dict[str, AbstractAgent] = {}  # agent_id -> agent instance
        self.graph: Dict[str, List[tuple[str, Optional[dict]]]] = defaultdict(list)  # agent_id -> [(next_agent_id, condition)]

    def add_agent(self, agent: AbstractAgent, dependencies: List[tuple[str, Optional[dict]]] = None):
        """Add an agent and its dependencies to the graph."""
        self.agents[agent.name] = agent
        if dependencies:
            self.graph[agent.name] = dependencies  # e.g., [("Tester_test1", {"status": "generated"})]
        self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")

    def remove_agent(self, agent_name: str):
        """Remove an agent and update the graph."""
        if agent_name in self.agents:
            self.agents[agent_name].stop()
            del self.agents[agent_name]
            self.graph.pop(agent_name, None)
            for src in self.graph:
                self.graph[src] = [(tgt, cond) for tgt, cond in self.graph[src] if tgt != agent_name]
            self.log_update(f"Removed agent {agent_name}")

    def update_agent(self, agent_name: str, new_agent: AbstractAgent):
        """Update an existing agent."""
        if agent_name in self.agents:
            self.agents[agent_name].stop()
            self.agents[agent_name] = new_agent
            new_agent.start()
            self.log_update(f"Updated agent {agent_name}")

    @abstractmethod
    def orchestrate(self, task: Task) -> tuple[str, str]:
        """Define how to traverse the agent graph and process the task."""
        pass

    def start(self):
        self.log_update("Starting aggregate")
        for agent in self.agents.values():
            agent.start()

    def stop(self):
        self.log_update("Stopping aggregate")
        for agent in self.agents.values():
            agent.stop()
