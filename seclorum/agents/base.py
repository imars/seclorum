# seclorum/agents/base.py (relevant parts)
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput
from seclorum.utils.logger import LoggerMixin
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory_manager import MemoryManager

class AbstractAgent(ABC, LoggerMixin):
    def __init__(self, name: str, session_id: str, quiet: bool = False):
        self.name: str = name
        super().__init__()
        self.session_id: str = session_id
        self.active: bool = False
        self.fs_manager = FileSystemManager()
        self.memory = MemoryManager(session_id)

    @abstractmethod
    def process_task(self, task: Task) -> Tuple[str, Any]:
        pass

    def start(self) -> None:
        self.active = True
        self.log_update(f"Starting {self.name}")

    def stop(self) -> None:
        self.active = False
        self.log_update(f"Stopping {self.name}")

    def commit_changes(self, message: str) -> None:
        self.fs_manager.commit_changes(message)

class AbstractAggregate(AbstractAgent):
    def __init__(self, session_id: str):
        super().__init__("Aggregate", session_id)
        self.agents: Dict[str, AbstractAgent] = {}
        self.graph: Dict[str, List[Tuple[str, Optional[Dict[str, Any]]]]] = defaultdict(list)
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def add_agent(self, agent: AbstractAgent, dependencies: Optional[List[Tuple[str, Optional[Dict[str, Any]]]]] = None) -> None:
        self.agents[agent.name] = agent
        self.graph[agent.name] = dependencies if dependencies is not None else []
        self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        if not condition:
            self.log_update("No condition to check, returning True")
            return True
        if "status" in condition and condition["status"] != status:
            self.log_update(f"Status mismatch: expected {condition['status']}, got {status}")
            return False
        if "passed" in condition and isinstance(result, TestResult) and condition["passed"] != result.passed:
            self.log_update(f"Passed mismatch: expected {condition['passed']}, got {result.passed}")
            return False
        self.log_update("Condition satisfied")
        return True

    def _propagate(self, current_agent: str, status: str, result: Any, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.log_update(f"Initializing task {task_id} in tasks")
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = result
        self.tasks[task_id]["outputs"][current_agent] = {"status": status, "result": result}
        self.logger.info(f"Task state after {current_agent}: {self.tasks[task_id]}")  # Elevated to INFO

        if stop_at == current_agent:
            self.log_update(f"Stopping at {current_agent} as requested")
            return status, result

        final_status, final_result = status, result
        dependents = self.graph.get(current_agent, [])
        self.logger.info(f"Checking dependents for {current_agent}: {dependents}")  # Elevated to INFO
        for next_agent_name, condition in dependents:
            if next_agent_name in self.tasks[task_id]["processed"]:
                self.log_update(f"Skipping already processed {next_agent_name}")
                continue
            self.logger.info(f"Evaluating condition for {next_agent_name}: {condition}")  # Elevated to INFO
            if self._check_condition(status, result, condition):
                next_agent = self.agents[next_agent_name]
                params: Dict[str, Any] = self.tasks[task_id]["outputs"].copy()
                self.logger.info(f"Propagating to {next_agent_name} with params: {params}")  # Elevated to INFO
                new_task = Task(task_id=task_id, description=task.description, parameters=params)
                new_status, new_result = next_agent.process_task(new_task)
                self.tasks[task_id]["processed"].add(next_agent_name)
                final_status, final_result = self._propagate(next_agent_name, new_status, new_result, task, stop_at)
        self.logger.info(f"Returning from _propagate for {current_agent}: status={final_status}")  # Elevated to INFO
        return final_status, final_result

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.log_update(f"Initializing task {task_id} at orchestration start")
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.log_update(f"Orchestrating task {task_id} with {len(self.agents)} agents, stopping at {stop_at}")

        pending_agents: Set[str] = set(self.agents.keys())
        while pending_agents:
            made_progress = False
            remaining_agents = list(pending_agents)
            self.log_update(f"Pending agents: {remaining_agents}")
            for agent_name in remaining_agents:
                if agent_name in self.tasks[task_id]["processed"]:
                    self.log_update(f"Agent {agent_name} already processed, skipping")
                    continue
                deps = self.graph[agent_name]
                deps_satisfied = True
                agent_outputs: Dict[str, Any] = self.tasks[task_id]["outputs"].copy()
                for dep_name, dep_conditions in deps:
                    if dep_name not in agent_outputs:
                        self.log_update(f"Dependency {dep_name} not satisfied for {agent_name}")
                        deps_satisfied = False
                        break
                    dep_output = agent_outputs[dep_name]
                    for key, value in dep_conditions.items():
                        if dep_output.get(key) != value:
                            self.log_update(f"Condition {key}={value} not met for {dep_name} in {agent_name}")
                            deps_satisfied = False
                            break
                if not deps_satisfied:
                    continue
                agent = self.agents[agent_name]
                self.log_update(f"Building parameters for {agent_name}: {agent_outputs}")
                new_task = Task(
                    task_id=task_id,
                    description=task.description,
                    parameters=agent_outputs
                )
                self.log_update(f"Processing {agent_name} for Task {task_id}")
                agent_status, agent_result = agent.process_task(new_task)
                final_status, final_result = self._propagate(agent_name, agent_status, agent_result, task, stop_at)
                self.tasks[task_id]["processed"].add(agent_name)
                made_progress = True
                if stop_at == agent_name:
                    self.log_update(f"Stopping orchestration at {agent_name}")
                    return final_status, final_result
            if not made_progress:
                self.log_update(f"No progress made with remaining agents {pending_agents}, exiting orchestration")
                break
            pending_agents -= self.tasks[task_id]["processed"]

        if final_status is None or final_result is None:  # Use final_status here
            raise ValueError(f"No agent processed task {task_id}")
        self.log_update(f"Orchestration complete, final status: {final_status}")
        return final_status, final_result
