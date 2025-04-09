# seclorum/agents/base.py
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
        self.logger.info(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        self.logger.info(f"Checking condition: status={status}, result={result}, condition={condition}")
        if not condition:
            self.logger.info("No condition to check, returning True")
            return True
        if "status" in condition and condition["status"] != status:
            self.logger.info(f"Status mismatch: expected {condition['status']}, got {status}")
            return False
        if "passed" in condition and isinstance(result, TestResult) and condition["passed"] == result.passed:  # Changed != to ==
            self.logger.info("Passed condition satisfied")
            return True
        self.logger.info("Condition not fully satisfied")
        return False

    def _propagate(self, current_agent: str, status: str, result: Any, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.logger.info(f"Initializing task {task_id} in tasks")
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = result
        self.tasks[task_id]["outputs"][current_agent] = {"status": status, "result": result}
        self.logger.info(f"Task state after {current_agent}: {self.tasks[task_id]}")
        print(f"[DEBUG PRINT] Task state after {current_agent}: {self.tasks[task_id]}")  # Fallback

        if stop_at == current_agent:
            self.logger.info(f"Stopping at {current_agent} as requested")
            return status, result

        final_status, final_result = status, result
        dependents = self.graph.get(current_agent, [])
        self.logger.info(f"Checking dependents for {current_agent}: {dependents}")
        print(f"[DEBUG PRINT] Checking dependents for {current_agent}: {dependents}")
        for next_agent_name, condition in dependents:
            if next_agent_name in self.tasks[task_id]["processed"]:
                self.logger.info(f"Skipping already processed {next_agent_name}")
                continue
            self.logger.info(f"Evaluating condition for {next_agent_name}: {condition}")
            print(f"[DEBUG PRINT] Evaluating condition for {next_agent_name}: {condition}")
            if self._check_condition(status, result, condition):
                next_agent = self.agents[next_agent_name]
                params: Dict[str, Any] = self.tasks[task_id]["outputs"].copy()
                self.logger.info(f"Propagating to {next_agent_name} with params: {params}")
                print(f"[DEBUG PRINT] Propagating to {next_agent_name}")
                new_task = Task(task_id=task_id, description=task.description, parameters=params)
                new_status, new_result = next_agent.process_task(new_task)
                self.tasks[task_id]["processed"].add(next_agent_name)
                final_status, final_result = self._propagate(next_agent_name, new_status, new_result, task, stop_at)
        self.logger.info(f"Returning from _propagate for {current_agent}: status={final_status}")
        print(f"[DEBUG PRINT] Returning from _propagate for {current_agent}: status={final_status}")
        return final_status, final_result

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        self.logger.info(f"Graph setup: {self.graph}")
        print(f"[DEBUG PRINT] Graph setup: {self.graph}")
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.logger.info(f"Initializing task {task_id} at orchestration start")
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.logger.info(f"Orchestrating task {task_id} with {len(self.agents)} agents, stopping at {stop_at}")

        final_status: Optional[str] = None
        final_result: Any = None
        pending_agents: Set[str] = set(self.agents.keys())
        self.logger.info(f"Initial pending agents: {pending_agents}")
        while pending_agents:
            made_progress = False
            for agent_name in list(pending_agents):
                if agent_name in self.tasks[task_id]["processed"]:
                    self.logger.info(f"Agent {agent_name} already processed, skipping")
                    continue
                deps = self.graph[agent_name]
                deps_satisfied = True
                agent_outputs: Dict[str, Any] = self.tasks[task_id]["outputs"].copy()
                self.logger.info(f"Dependencies for {agent_name}: {deps}")
                for dep_name, dep_conditions in deps:
                    if dep_name not in agent_outputs:
                        self.logger.info(f"Dependency {dep_name} not satisfied for {agent_name}")
                        deps_satisfied = False
                        break
                    dep_output = agent_outputs[dep_name]
                    for key, value in dep_conditions.items():
                        if dep_output.get(key) != value:
                            self.logger.info(f"Condition {key}={value} not met for {dep_name} in {agent_name}")
                            deps_satisfied = False
                            break
                if not deps_satisfied:
                    continue
                agent = self.agents[agent_name]
                self.logger.info(f"Building parameters for {agent_name}: {agent_outputs}")
                new_task = Task(
                    task_id=task_id,
                    description=task.description,
                    parameters=agent_outputs
                )
                self.logger.info(f"Processing {agent_name} for Task {task_id}")
                agent_status, agent_result = agent.process_task(new_task)
                final_status, final_result = self._propagate(agent_name, agent_status, agent_result, task, stop_at)
                self.tasks[task_id]["processed"].add(agent_name)
                made_progress = True
                if stop_at == agent_name:
                    self.logger.info(f"Stopping orchestration at {agent_name}")
                    return final_status, final_result
            if not made_progress:
                self.logger.info(f"No progress made with remaining agents {pending_agents}, exiting orchestration")
                break
            pending_agents -= self.tasks[task_id]["processed"]
            self.logger.info(f"Updated pending agents: {pending_agents}")

        if final_status is None or final_result is None:
            raise ValueError(f"No agent processed task {task_id}")
        self.logger.info(f"Orchestration complete, final status: {final_status}")
        return final_status, final_result
