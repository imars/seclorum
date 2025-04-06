# seclorum/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput
from seclorum.utils.logger import LoggerMixin
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory_manager import MemoryManager  # Direct import

class AbstractAgent(ABC, LoggerMixin):
    def __init__(self, name: str, session_id: str, quiet: bool = False):
        self.name = name
        super().__init__()
        self.session_id = session_id
        self.active = False
        self.fs_manager = FileSystemManager()
        self.memory = MemoryManager(session_id)

    @abstractmethod
    def process_task(self, task: Task) -> Tuple[str, Any]:
        pass

    def start(self):
        self.active = True
        self.log_update(f"Starting {self.name}")

    def stop(self):
        self.active = False
        self.log_update(f"Stopping {self.name}")

    def commit_changes(self, message: str):
        self.fs_manager.commit_changes(message)

class AbstractAggregate(AbstractAgent):
    def __init__(self, session_id: str):
        super().__init__("Aggregate", session_id)
        self.agents: Dict[str, AbstractAgent] = {}
        self.graph: Dict[str, List[Tuple[str, Optional[Dict[str, Any]]]]] = defaultdict(list)
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def add_agent(self, agent: AbstractAgent, dependencies: List[Tuple[str, Optional[Dict[str, Any]]]] = None):
        self.agents[agent.name] = agent
        self.graph[agent.name] = dependencies if dependencies is not None else []
        self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        if not condition:
            return True
        if "status" in condition and condition["status"] != status:
            return False
        if "passed" in condition and isinstance(result, TestResult) and condition["passed"] != result.passed:
            return False
        return True

    def _propagate(self, current_agent: str, status: str, result: Any, task: Task):
        task_id = task.task_id
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = result
        if "outputs" not in self.tasks[task_id]:
            self.tasks[task_id]["outputs"] = {}
        if isinstance(result, CodeOutput):
            self.tasks[task_id]["outputs"]["code_output"] = result.model_dump()
        elif isinstance(result, TestResult):
            self.tasks[task_id]["outputs"]["test_result"] = result.model_dump()
        self.logger.debug(f"Updated task {task_id}: {self.tasks[task_id]}")

        for next_agent_name, condition in self.graph.get(current_agent, []):
            if self._check_condition(status, result, condition):
                next_agent = self.agents[next_agent_name]
                params = self.tasks[task_id]["outputs"].copy()
                if "error" in condition:
                    params["error"] = condition["error"]
                new_task = Task(task_id=task_id, description=task.description, parameters=params)
                new_status, new_result = next_agent.process_task(new_task)
                self._propagate(next_agent_name, new_status, new_result, task)

    def orchestrate(self, task: Task) -> Tuple[str, Any]:
        task_id = task.task_id
        if task_id not in self.tasks:
            self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": "assigned", "result": None, "outputs": {}}
        self.logger.info(f"Task {task_id} assigned or resumed with status {self.tasks[task_id]['status']}")

        processed = set()
        latest_result = None
        while True:
            made_progress = False
            for agent_name, deps in self.graph.items():
                if agent_name in processed:
                    continue
                deps_satisfied = True
                for dep_agent, condition in deps:
                    if dep_agent not in self.graph or dep_agent not in processed or not self._check_condition(self.tasks[task_id]["status"], self.tasks[task_id]["result"], condition):
                        deps_satisfied = False
                        break
                if deps_satisfied:
                    agent = self.agents[agent_name]
                    params = self.tasks[task_id].get("outputs", {}).copy()
                    new_task = Task(task_id=task_id, description=task.description, parameters=params)
                    status, result = agent.process_task(new_task)
                    self._propagate(agent_name, status, result, task)
                    processed.add(agent_name)
                    made_progress = True
                    latest_result = result
            if not made_progress:
                break

        final_status = self.tasks[task_id]["status"]
        return final_status, latest_result
