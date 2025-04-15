from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput, Plan
from seclorum.utils.logger import LoggerMixin
from seclorum.models.manager import ModelManager, create_model_manager
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory.core import Memory
from seclorum.agents.remote import Remote
import logging
import requests
import os
import time
import timeout_decorator

class AbstractAgent(ABC, LoggerMixin):
    _memory_cache = {}

    def __init__(self, name: str, session_id: str, quiet: bool = False):
        self.name: str = name
        super().__init__()
        self.session_id: str = session_id
        self.active: bool = False
        self.fs_manager = FileSystemManager(require_git=quiet)
        self.memory = self.get_or_create_memory(session_id)
        self.logger.info(f"Using shared MemoryManager for session {session_id}")
        self._flow_tracker = []

    @classmethod
    def get_or_create_memory(cls, session_id: str) -> Memory:
        if session_id not in cls._memory_cache:
            cls._memory_cache[session_id] = Memory(session_id, disable_embedding=True)
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
        self.log_update(f"Committing changes: {message}")
        return self.fs_manager.commit_changes(f"{self.name}: {message}")

    @timeout_decorator.timeout(5, timeout_exception=TimeoutError)
    def save_output(self, task: Task, output: Any, status: str = "completed") -> None:
        self.log_update(f"Saving output for task {task.task_id}: status={status}, output_type={type(output).__name__}")
        try:
            start_time = time.time()
            self.memory.save(
                prompt=task.description,
                response=output,
                task_id=task.task_id,
                agent_name=self.name
            )
            elapsed = time.time() - start_time
            self.log_update(f"Saved output in {elapsed:.2f}s")
        except Exception as e:
            self.log_update(f"Failed to save output: {str(e)}")
        self.store_output(task, status, output)

    def track_flow(self, task: Task, status: str, result: Any, use_remote: bool):
        passed = False
        try:
            passed = isinstance(result, TestResult) and result.passed or bool(getattr(result, 'code', '').strip())
        except Exception as e:
            self.log_update(f"Error evaluating flow passed status: {str(e)}")
        flow_entry = {
            "agent_name": self.name,
            "task_id": task.task_id,
            "session_id": self.session_id,
            "remote": use_remote,
            "passed": passed,
            "status": status
        }
        self._flow_tracker.append(flow_entry)
        self.log_update(f"Tracked flow: {flow_entry}")

    @timeout_decorator.timeout(10, timeout_exception=TimeoutError)
    def infer(self, prompt: str, task: Task, use_remote: Optional[bool] = None, use_context: bool = False, endpoint: str = "google_ai_studio", **kwargs) -> str:
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
        start_time = time.time()
        try:
            result = self._run_inference(full_prompt, use_remote, endpoint, **kwargs)
        except Exception as e:
            self.log_update(f"Inference failed: {str(e)}, returning empty result")
            result = ""
        elapsed = time.time() - start_time
        self.log_update(f"Inference completed in {elapsed:.2f}s, result_length={len(result)}")
        return result

    def _run_inference(self, prompt: str, use_remote: bool, endpoint: str, **kwargs) -> str:
        self.log_update(f"Running inference: remote={use_remote}, endpoint={endpoint}")
        if use_remote:
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
            self.log_update(f"Sending request to {url}")
            try:
                response = requests.post(url, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                self.log_update(f"Remote inference successful: {text[:50]}...")
                return text
            except requests.RequestException as e:
                self.log_update(f"Remote inference failed: {str(e)}")
                raise
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}")

    def add_model(self, model_key: str, model_manager: ModelManager) -> None:
        self.available_models[model_key] = model_manager
        self.log_update(f"Added model '{model_key}' to {self.name}: {model_manager.model_name}")

    def switch_model(self, model_key: str) -> None:
        if model_key not in self.available_models:
            raise ValueError(f"Model '{model_key}' not found in available models: {list(self.available_models.keys())}")
        self.current_model_key = model_key
        self.model = self.available_models[model_key]
        self.log_update(f"Switched {self.name} to model '{model_key}': {self.model.model_name}")

    def select_model(self, task: Task) -> None:
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
        self.log_update(f"Inferring with model '{self.current_model_key}' on prompt: {prompt[:50]}...")
        return super().infer(prompt, task, use_remote=use_remote, use_context=use_context, endpoint=endpoint, **kwargs)

    def process_task(self, task: Task) -> Tuple[str, Any]:
        raise NotImplementedError("Subclasses must implement process_task")

    def store_output(self, task: Task, status: str, result: Any):
        agent_key = f"{self.name}"
        task.parameters[agent_key] = {"status": status, "result": result}
        self.log_update(f"Stored output for {self.name}: status={status}, result_type={type(result).__name__}")

class Aggregate(Agent):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__("Aggregate", session_id, model_manager)
        self.agents: Dict[str, AbstractAgent] = {}
        self.graph: Dict[str, List[Tuple[str, Optional[Dict[str, Any]]]]] = defaultdict(list)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.max_subtasks = 10

    def add_agent(self, agent: AbstractAgent, dependencies: Optional[List[Tuple[str, Optional[Dict[str, Any]]]]] = None) -> None:
        self.agents[agent.name] = agent
        self.graph[agent.name] = dependencies if dependencies is not None else []
        self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")

    def _check_condition(self, status: str, result: Any, condition: Optional[Dict[str, Any]]) -> bool:
        self.log_update(f"Checking condition: status={status}, result_type={type(result).__name__}, condition={condition}")
        if not condition:
            return True
        if "status" in condition and condition["status"] != status:
            self.log_update(f"Condition failed: expected status {condition['status']}, got {status}")
            return False
        if "passed" in condition and isinstance(result, TestResult):
            passed = condition["passed"] == result.passed
            self.log_update(f"Passed condition: expected {condition['passed']}, got {result.passed}")
            return passed
        return True

    def _propagate(self, current_agent: str, status: str, result: Any, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}

        final_status, final_result = status, result
        self.log_update(f"Propagating from {current_agent}: status={status}, result_type={type(result).__name__}")

        if isinstance(result, Plan):
            self.log_update(f"Handling Plan from {current_agent} with {len(result.subtasks)} subtasks")
            self.tasks[task_id]["outputs"][current_agent] = {"status": status, "result": result}
            task.parameters[current_agent] = {"status": status, "result": result}
            subtask_count = 0
            for subtask in result.subtasks:
                if subtask_count >= self.max_subtasks:
                    self.log_update(f"Reached max subtasks ({self.max_subtasks}), stopping")
                    break
                subtask_count += 1
                subtask_id = subtask.task_id
                self.log_update(f"Processing subtask {subtask_id}: description={subtask.description[:50]}, "
                               f"parameters={subtask.parameters}")
                if subtask_id not in self.tasks:
                    self.tasks[subtask_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
                dependents = self.graph.get(current_agent, [])
                self.log_update(f"Dependents for {current_agent}: {dependents}")
                for next_agent_name, condition in dependents:
                    if next_agent_name in self.tasks[subtask_id]["processed"]:
                        self.log_update(f"Skipping processed agent {next_agent_name} for subtask {subtask_id}")
                        continue
                    if self._check_condition(status, result, condition):
                        next_agent = self.agents.get(next_agent_name)
                        if not next_agent:
                            self.log_update(f"Agent {next_agent_name} not found")
                            continue
                        params = self.tasks[task_id]["outputs"].copy()
                        new_task = Task(
                            task_id=subtask_id,
                            description=subtask.description,
                            parameters={**subtask.parameters, **params}
                        )
                        self.log_update(f"Executing {next_agent_name} for subtask {subtask_id} with params: {new_task.parameters}")
                        try:
                            start_time = time.time()
                            new_status, new_result = next_agent.process_task(new_task)
                            elapsed = time.time() - start_time
                            next_agent.track_flow(new_task, new_status, new_result, new_task.parameters.get("use_remote", False))
                            self.tasks[subtask_id]["processed"].add(next_agent_name)
                            self.tasks[subtask_id]["outputs"][next_agent_name] = {"status": new_status, "result": new_result}
                            task.parameters[next_agent_name] = {"status": new_status, "result": new_result}
                            final_status, final_result = new_status, new_result
                            self.log_update(f"{next_agent_name} completed subtask {subtask_id}: status={new_status}, "
                                           f"result_type={type(new_result).__name__}, time={elapsed:.2f}s")
                        except Exception as e:
                            self.log_update(f"Error in {next_agent_name} for subtask {subtask_id}: {str(e)}")
                            final_status, final_result = "failed", None
                    else:
                        self.log_update(f"Condition not met for {next_agent_name} in subtask {subtask_id}: {condition}")
        else:
            self.tasks[task_id]["status"] = status
            self.tasks[task_id]["result"] = result
            self.tasks[task_id]["outputs"][current_agent] = {"status": status, "result": result}
            task.parameters[current_agent] = {"status": status, "result": result}
            dependents = self.graph.get(current_agent, [])
            self.log_update(f"Non-Plan dependents for {current_agent}: {dependents}")
            for next_agent_name, condition in dependents:
                if next_agent_name in self.tasks[task_id]["processed"]:
                    continue
                if self._check_condition(status, result, condition):
                    next_agent = self.agents.get(next_agent_name)
                    if not next_agent:
                        self.log_update(f"Agent {next_agent_name} not found")
                        continue
                    params = self.tasks[task_id]["outputs"].copy()
                    new_task = Task(task_id=task_id, description=task.description, parameters=params)
                    self.log_update(f"Executing {next_agent_name} for task {task_id}")
                    try:
                        start_time = time.time()
                        new_status, new_result = next_agent.process_task(new_task)
                        elapsed = time.time() - start_time
                        next_agent.track_flow(new_task, new_status, new_result, new_task.parameters.get("use_remote", False))
                        self.tasks[task_id]["processed"].add(next_agent_name)
                        final_status, final_result = self._propagate(next_agent_name, new_status, new_result, task, stop_at)
                        self.log_update(f"{next_agent_name} completed: time={elapsed:.2f}s")
                    except Exception as e:
                        self.log_update(f"Error in {next_agent_name}: {str(e)}")
                        final_status, final_result = "failed", None

        self.log_update(f"Propagation complete from {current_agent}: status={final_status}, result_type={type(final_result).__name__}")
        if stop_at == current_agent:
            return status, result
        return final_status, final_result

    def process_task(self, task: Task) -> Tuple[str, Any]:
        self.log_update(f"Starting process_task for task={task.task_id}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        task_id: str = task.task_id
        if task_id not in self.tasks:
            self.tasks[task_id] = {"status": None, "result": None, "outputs": {}, "processed": set()}
        self.log_update(f"Orchestrating task {task_id} with {len(self.agents)} agents, stopping at {stop_at}")

        final_status: Optional[str] = None
        final_result: Any = None
        pending_agents: Set[str] = set(self.agents.keys())
        self.log_update(f"Pending agents: {pending_agents}")
        max_iterations = 10

        iteration = 0
        while pending_agents and iteration < max_iterations:
            iteration += 1
            self.log_update(f"Iteration {iteration}, pending agents: {pending_agents}")
            next_agent_name = self.decide_next_step(task, pending_agents)
            self.log_update(f"Decided next agent: {next_agent_name}")
            if not next_agent_name or next_agent_name not in self.agents:
                self.log_update(f"No valid next agent, trying first available: {pending_agents}")
                next_agent_name = next(iter(pending_agents), None)
                if not next_agent_name:
                    break
            if next_agent_name in self.tasks[task_id]["processed"]:
                self.log_update(f"Agent {next_agent_name} already processed, removing")
                pending_agents.remove(next_agent_name)
                continue
            deps = self.graph.get(next_agent_name, [])
            agent_outputs = self.tasks[task_id]["outputs"].copy()
            deps_satisfied = all(
                dep_name in agent_outputs and
                self._check_condition(agent_outputs[dep_name]["status"], agent_outputs[dep_name]["result"], condition)
                for dep_name, condition in deps
            )
            self.log_update(f"Dependencies for {next_agent_name}: {deps}, satisfied={deps_satisfied}")
            if not deps_satisfied:
                self.log_update(f"Dependencies not satisfied for {next_agent_name}, trying next agent")
                continue
            agent = self.agents[next_agent_name]
            new_task = Task(task_id=task_id, description=task.description, parameters=agent_outputs)
            self.log_update(f"Executing agent {next_agent_name} with params: {new_task.parameters}")
            try:
                start_time = time.time()
                agent_status, agent_result = agent.process_task(new_task)
                elapsed = time.time() - start_time
                self.log_update(f"Agent {next_agent_name} returned status={agent_status}, result_type={type(agent_result).__name__}, time={elapsed:.2f}s")
                agent.track_flow(new_task, agent_status, agent_result, new_task.parameters.get("use_remote", False))
                final_status, final_result = self._propagate(next_agent_name, agent_status, agent_result, task, stop_at)
                self.tasks[task_id]["processed"].add(next_agent_name)
                pending_agents.remove(next_agent_name)
            except Exception as e:
                self.log_update(f"Error processing agent {next_agent_name}: {str(e)}")
                final_status, final_result = "failed", None
                break
            if stop_at == next_agent_name:
                self.log_update(f"Stopping at {next_agent_name}")
                return final_status, final_result

        if final_status is None or final_result is None:
            self.log_update(f"No agent processed task {task_id}, checking processed agents: {self.tasks[task_id]['processed']}")
            if self.tasks[task_id]["processed"]:
                last_agent = max(self.tasks[task_id]["processed"], key=lambda x: self.tasks[task_id]["outputs"].get(x, {}).get("timestamp", 0))
                final_status = self.tasks[task_id]["outputs"].get(last_agent, {}).get("status", "failed")
                final_result = self.tasks[task_id]["outputs"].get(last_agent, {}).get("result")
                self.log_update(f"Using last processed agent {last_agent}: status={final_status}")
            else:
                raise ValueError(f"No agent processed task {task_id}")
        self.log_update(f"Orchestration complete, final status: {final_status}")
        return final_status, final_result

    def decide_next_step(self, task: Task, pending_agents: Set[str]) -> Optional[str]:
        task_id = task.task_id
        self.log_update(f"Deciding next step for task {task_id}, pending agents: {pending_agents}")
        for agent_name in pending_agents:
            deps = self.graph.get(agent_name, [])
            agent_outputs = self.tasks.get(task_id, {}).get("outputs", {})
            deps_satisfied = all(
                dep_name in agent_outputs and
                self._check_condition(agent_outputs[dep_name]["status"], agent_outputs[dep_name]["result"], condition)
                for dep_name, condition in deps
            )
            if deps_satisfied:
                self.log_update(f"Selected agent {agent_name} with satisfied dependencies")
                return agent_name
        self.log_update(f"No agent with satisfied dependencies, falling back to inference")
        try:
            start_time = time.time()
            prompt = (
                f"Given the task '{task.description}' and current state:\n"
                f"Status: {self.tasks.get(task_id, {}).get('status')}\n"
                f"Processed agents: {list(self.tasks.get(task_id, {}).get('processed', set()))}\n"
                f"Outputs: {self.tasks.get(task_id, {}).get('outputs', {})}\n"
                f"Pending agents: {list(pending_agents)}\n"
                f"Graph: {self.graph}\n"
                "Which agent should process the task next? Return only the agent name or 'None' if no step is clear."
            )
            decision = self.infer(prompt, task).strip()
            elapsed = time.time() - start_time
            self.log_update(f"Inference decided next step: {decision}, time={elapsed:.2f}s")
            if decision == "None" or decision not in pending_agents:
                return None
            return decision
        except Exception as e:
            self.log_update(f"Error in decide_next_step inference: {str(e)}")
            return None
