# seclorum/agents/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput
from seclorum.utils.logger import LoggerMixin
from seclorum.models.manager import ModelManager, create_model_manager
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory.core import Memory
from seclorum.agents.remote import Remote
import logging
import requests
import os

class AbstractAgent(ABC, LoggerMixin):
    _memory_cache = {}  # Class-level cache for MemoryManager

    def __init__(self, name: str, session_id: str, quiet: bool = False):
        self.name: str = name
        super().__init__()
        self.session_id: str = session_id
        self.active: bool = False
        self.fs_manager = FileSystemManager(require_git=quiet)
        self.memory = self.get_or_create_memory(session_id)
        self.logger.info(f"Using shared MemoryManager for session {session_id}")
        self._flow_tracker = []  # Track agent visits for testing

    @classmethod
    def get_or_create_memory(cls, session_id: str) -> Memory:
        if session_id not in cls._memory_cache:
            cls._memory_cache[session_id] = Memory(session_id)
        return cls._memory_cache[session_id]

    @abstractmethod
    def process_task(self, task: Task) -> Tuple[str, Any]:
        pass

    def start(self) -> None:
        self.active = True
        self.log_update(f"Starting {self.name}")

    def stop(self) -> None:
        self.active = False
        self.memory.stop()
        self.log_update(f"Stopping {self.name}")

    def commit_changes(self, message: str) -> bool:
        """Commit changes to the Git repository with agent prefix."""
        return self.fs_manager.commit_changes(f"{self.name}: {message}")

    def save_output(self, task: Task, output: Any, status: str = "completed") -> None:
        """Save output to memory and task parameters."""
        self.memory.save(
            prompt=task.description,
            response=output,
            task_id=task.task_id,
            agent_name=self.name
        )
        self.store_output(task, status, output)
        self.log_update(f"Saved output for task {task.task_id}: {status}")

    def track_flow(self, task: Task, status: str, result: Any, use_remote: bool):
        """Track agent visit for flow testing."""
        self._flow_tracker.append({
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "passed": isinstance(result, TestResult) and result.passed or bool(getattr(result, 'code', '').strip()),
            "status": status
        })

    def infer(self, prompt: str, task: Task, use_remote: Optional[bool] = None, use_context: bool = False, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Run inference with optional history and similar tasks."""
        use_remote = use_remote if use_remote is not None else task.parameters.get("use_remote", False)
        if use_context:
            history = self.memory.load_conversation_history(task_id=task.task_id, agent_name=self.name)
            formatted_history = self.memory.format_history(history) if history else ""
            similar_tasks = self.memory.find_similar(task.description, task_id=None, n_results=3)
            formatted_similar = "\n".join(f"- {task}" for task in similar_tasks) if similar_tasks else ""

            context = []
            if formatted_similar:
                context.append(f"Relevant Past Tasks:\n{formatted_similar}")
            if formatted_history:
                context.append(f"Task History:\n{formatted_history}")
            context.append(f"Current Prompt:\n{prompt}")
            full_prompt = "\n\n".join(context) if context else prompt
        else:
            full_prompt = prompt

        self.log_update(f"Inferring {'with context ' if use_context else ''}(length: {len(full_prompt)} chars, remote: {use_remote})")
        return self._run_inference(full_prompt, use_remote, endpoint, **kwargs)

    def _run_inference(self, prompt: str, use_remote: bool, endpoint: str, **kwargs) -> str:
        """Helper method to handle inference with logging."""
        if use_remote:
            self.log_update(f"Running remote inference to {endpoint}")
            return self.remote_infer(prompt, endpoint=endpoint, **kwargs)
        return self.model.generate(prompt, **kwargs)

class Agent(AbstractAgent, Remote):
    def __init__(self, name: str, session_id: str, model_manager: Optional[ModelManager] = None, model_name: str = "llama3.2:latest"):
        super().__init__(name, session_id)
        self.logger = logging.getLogger(f"Agent_{name}")
        self.model = model_manager or create_model_manager(provider="ollama", model_name=model_name)
        self.available_models = {"default": self.model}
        self.current_model_key = "default"
        self.memory = self.get_or_create_memory(session_id)
        self.log_update(f"Agent {name} initialized with model {self.model.model_name}")

    def remote_infer(self, prompt: str, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Run inference remotely with logging for rate limits."""
        self.log_update(f"Running remote inference to {endpoint}")
        if endpoint == "google_ai_studio":
            api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 512, "temperature": 0.7}
            }
            try:
                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result["candidates"][0]["content"]["parts"][0]["text"]
            except requests.RequestException as e:
                self.log_update(f"Remote inference failed: {str(e)}")
                raise
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

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
        model_key = self.infer(prompt, task).strip()
        if model_key in self.available_models:
            self.switch_model(model_key)
        else:
            self.log_update(f"Model '{model_key}' not found, sticking with '{self.current_model_key}'")

    def infer(self, prompt: str, task: Task, use_remote: Optional[bool] = None, use_context: bool = False, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Run inference with the current active model, supporting task and context."""
        self.log_update(f"Inferring with model '{self.current_model_key}' on prompt: {prompt[:50]}...")
        return super().infer(prompt, task, use_remote=use_remote, use_context=use_context, endpoint=endpoint, **kwargs)

    def process_task(self, task: Task) -> Tuple[str, Any]:
        """Base implementation; override in subclasses."""
        raise NotImplementedError("Subclasses must implement process_task")

    def store_output(self, task: Task, status: str, result: Any):
        """Store agent output in task parameters with a consistent key."""
        agent_key = f"{self.name}"
        task.parameters[agent_key] = {"status": status, "result": result}
        self.log_update(f"Stored output for {self.name}: {status}, {result}")

class Aggregate(Agent):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__("Aggregate", session_id, model_manager)
        self.agents: Dict[str, AbstractAgent] = {}
        self.graph: Dict[str, List[Tuple[str, Optional[Dict[str, Any]]]]] = defaultdict(list)
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def add_agent(self, agent: AbstractAgent, dependencies: Optional[List[Tuple[str, Optional[Dict[str, Any]]]]] = None) -> None:
        self.agents[agent.name] = agent
        self.graph[agent.name] = dependencies if dependencies is not None else []
        self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        self.log_update(f"Evaluating condition: status={status}, result={result}, condition={condition}")
        if not condition:
            return True
        if "status" in condition and condition["status"] != status:
            return False
        if "passed" in condition and isinstance(result, TestResult):
            return condition["passed"] == result.passed
        return True

    def _propagate(self, current_agent: str, status: str, result: Any, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.tasks[task_id]["status"] = status
        self.tasks[task_id]["result"] = result
        self.tasks[task_id]["outputs"][current_agent] = {"status": status, "result": result}
        self.log_update(f"Task state after {current_agent}: {self.tasks[task_id]}")

        if stop_at == current_agent:
            return status, result

        final_status, final_result = status, result
        dependents = self.graph.get(current_agent, [])
        for next_agent_name, condition in dependents:
            if next_agent_name in self.tasks[task_id]["processed"]:
                continue
            if self._check_condition(status, result, condition):
                next_agent = self.agents[next_agent_name]
                params = self.tasks[task_id]["outputs"].copy()
                new_task = Task(task_id=task_id, description=task.description, parameters=params)
                new_status, new_result = next_agent.process_task(new_task)
                next_agent.track_flow(new_task, new_status, new_result, new_task.parameters.get("use_remote", False))
                self.tasks[task_id]["processed"].add(next_agent_name)
                final_status, final_result = self._propagate(next_agent_name, new_status, new_result, task, stop_at)
        return final_status, final_result

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.log_update(f"Orchestrating task {task_id} with {len(self.agents)} agents, stopping at {stop_at}")

        final_status: Optional[str] = None
        final_result: Any = None
        pending_agents: Set[str] = set(self.agents.keys())

        while pending_agents:
            next_agent_name = self.decide_next_step(task, pending_agents)
            if not next_agent_name:
                break
            if next_agent_name in self.tasks[task_id]["processed"]:
                pending_agents.remove(next_agent_name)
                continue
            deps = self.graph[next_agent_name]
            agent_outputs = self.tasks[task_id]["outputs"].copy()
            deps_satisfied = all(
                dep_name in agent_outputs and
                self._check_condition(agent_outputs[dep_name]["status"], agent_outputs[dep_name]["result"], condition)
                for dep_name, condition in deps
            )
            if not deps_satisfied:
                pending_agents.remove(next_agent_name)
                continue
            agent = self.agents[next_agent_name]
            new_task = Task(task_id=task_id, description=task.description, parameters=agent_outputs)
            agent_status, agent_result = agent.process_task(new_task)
            agent.track_flow(new_task, agent_status, agent_result, new_task.parameters.get("use_remote", False))
            final_status, final_result = self._propagate(next_agent_name, agent_status, agent_result, task, stop_at)
            self.tasks[task_id]["processed"].add(next_agent_name)
            if stop_at == next_agent_name:
                return final_status, final_result
            pending_agents.remove(next_agent_name)

        if final_status is None or final_result is None:
            raise ValueError(f"No agent processed task {task_id}")
        self.log_update(f"Orchestration complete, final status: {final_status}")
        return final_status, final_result

    def decide_next_step(self, task: Task, pending_agents: Set[str]) -> Optional[str]:
        task_id = task.task_id
        if task_id not in self.tasks:
            return next(iter(pending_agents), None)
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
        decision = self.infer(prompt, task).strip()
        self.log_update(f"Decided next step for task {task_id}: {decision}")
        if decision == "None" or decision not in pending_agents:
            return next(iter(pending_agents), None)
        return decision
