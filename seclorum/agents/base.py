# seclorum/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput
from seclorum.utils.logger import LoggerMixin
from seclorum.models.manager import ModelManager, create_model_manager
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

class Agent(AbstractAgent):
    def __init__(self, name: str, session_id: str, model_manager: Optional[ModelManager] = None, model_name: str = "llama3.2:latest"):
        super().__init__(name, session_id)
        self.model = model_manager or create_model_manager(provider="ollama", model_name=model_name)
        self.available_models = {"default": self.model}
        self.current_model_key = "default"
        self.log_update(f"Agent {name} initialized with model {self.model.model_name}")

    def add_model(self, model_key: str, model_manager: ModelManager) -> None:
        """Add a new model to the agent's model pool."""
        self.available_models[model_key] = model_manager
        self.log_update(f"Added model '{model_key}' to {self.name}: {model_manager.model_name}")

    def switch_model(self, model_key: str) -> None:
        """Switch the active model for inference."""
        if model_key not in self.available_models:
            raise ValueError(f"Model '{model_key}' not found in available models: {list(self.available_models.keys())}")
        self.current_model_key = model_key
        self.model = self.available_models[model_key]
        self.log_update(f"Switched {self.name} to model '{model_key}': {self.model.model_name}")

    def select_model(self, task: Task) -> None:
        """Intelligently select a model based on task requirements."""
        prompt = (
            f"Given the task '{task.description}', available models: {list(self.available_models.keys())}, "
            "which model should be used? Return only the model key."
        )
        model_key = self.infer(prompt).strip()
        if model_key in self.available_models:
            self.switch_model(model_key)
        else:
            self.log_update(f"Model '{model_key}' not found, sticking with '{self.current_model_key}'")

    def infer(self, prompt: str, **kwargs) -> str:
        """Run inference with the current active model."""
        self.log_update(f"Inferring with model '{self.current_model_key}' on prompt: {prompt[:50]}...")
        return self.model.generate(prompt, **kwargs)

    def process_task(self, task: Task) -> Tuple[str, Any]:
        """Base implementation; override in subclasses."""
        raise NotImplementedError("Subclasses must implement process_task")

class Aggregate(Agent):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__("Aggregate", session_id, model_manager)
        self.agents: Dict[str, AbstractAgent] = {}
        self.graph: Dict[str, List[Tuple[str, Optional[Dict[str, Any]]]]] = defaultdict(list)
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def add_agent(self, agent: AbstractAgent, dependencies: Optional[List[Tuple[str, Optional[Dict[str, Any]]]]] = None) -> None:
        self.agents[agent.name] = agent
        self.graph[agent.name] = dependencies if dependencies is not None else []
        self.logger.info(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        self.logger.info(f"Evaluating condition: status={status}, result={result}, condition={condition}")
        if not condition:
            self.logger.info("No condition provided, defaulting to True")
            return True

        # Status check
        if "status" in condition:
            if condition["status"] != status:
                self.logger.info(f"Status mismatch: expected {condition['status']}, got {status}")
                return False
            self.logger.info(f"Status satisfied: {status}")

        # Passed check
        if "passed" in condition and isinstance(result, TestResult):
            expected = condition["passed"]
            actual = result.passed
            self.logger.info(f"Checking passed: expected={expected}, got={actual}")
            if expected == actual:
                self.logger.info("Passed condition met")
                return True
            else:
                self.logger.info(f"Passed condition not met: expected {expected}, got {actual}")
                return False

        self.logger.info("All conditions checked, defaulting to True")
        return True

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
            next_agent_name = self.decide_next_step(task, pending_agents)
            if not next_agent_name:
                self.logger.info(f"No next step decided, exiting with remaining agents: {pending_agents}")
                break

            if next_agent_name in self.tasks[task_id]["processed"]:
                self.logger.info(f"Agent {next_agent_name} already processed, skipping")
                pending_agents.remove(next_agent_name)
                continue

            # Check dependencies
            deps = self.graph[next_agent_name]
            agent_outputs: Dict[str, Any] = self.tasks[task_id]["outputs"].copy()
            deps_satisfied = all(
                dep_name in agent_outputs and
                self._check_condition(agent_outputs[dep_name]["status"], agent_outputs[dep_name]["result"], condition)
                for dep_name, condition in deps
            )
            if not deps_satisfied:
                self.logger.info(f"Dependencies not satisfied for {next_agent_name}, re-evaluating")
                pending_agents.remove(next_agent_name)  # Temporarily skip, re-evaluate next iteration
                continue

            # Process the chosen agent
            agent = self.agents[next_agent_name]
            self.logger.info(f"Processing {next_agent_name} for Task {task_id}")
            new_task = Task(task_id=task_id, description=task.description, parameters=agent_outputs)
            agent_status, agent_result = agent.process_task(new_task)
            final_status, final_result = self._propagate(next_agent_name, agent_status, agent_result, task, stop_at)
            self.tasks[task_id]["processed"].add(next_agent_name)

            if stop_at == next_agent_name:
                self.logger.info(f"Stopping orchestration at {next_agent_name}")
                return final_status, final_result

            pending_agents.remove(next_agent_name)
            self.logger.info(f"Updated pending agents: {pending_agents}")

        if final_status is None or final_result is None:
            raise ValueError(f"No agent processed task {task_id}")
        self.logger.info(f"Orchestration complete, final status: {final_status}")
        return final_status, final_result

    def decide_next_step(self, task: Task, pending_agents: Set[str]) -> Optional[str]:
        """
        Decide the next agent to process based on task state and graph dependencies.
        Returns None if no suitable next step is found.
        """
        task_id = task.task_id
        if task_id not in self.tasks:
            self.logger.info(f"Task {task_id} not initialized, defaulting to first agent")
            return next(iter(pending_agents), None)

        # Build prompt for intelligent decision
        current_state = self.tasks[task_id]
        prompt = (
            f"Given the task '{task.description}' and current state:\n"
            f"Status: {current_state['status']}\n"
            f"Processed agents: {list(current_state['processed'])}\n"
            f"Outputs: {current_state['outputs']}\n"
            f"Pending agents: {list(pending_agents)}\n"
            f"Graph: {self.graph}\n"
            "Which agent should process the task next? Return only the agent name or 'None' if no step is clear."
        )
        decision = self.infer(prompt).strip()
        self.logger.info(f"Decided next step for task {task_id}: {decision}")

        # Validate decision
        if decision == "None" or decision not in pending_agents:
            self.logger.info(f"No valid next step decided, falling back to first available")
            return next(iter(pending_agents), None)
        return decision
