from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput, Plan
from seclorum.agents.base import AbstractAgent
from seclorum.agents.agent import Agent
from seclorum.utils.logger import LoggerMixin
from seclorum.models.manager import ModelManager, create_model_manager
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory.memory import Memory
from seclorum.agents.remote import Remote
import logging
import requests
import os
import time
import timeout_decorator

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
            metadata = getattr(result, "metadata", {})
            if metadata.get("error"):
                self.log_update(f"Skipping invalid Plan from {current_agent}: {metadata['error']}")
                return final_status, final_result
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
                               f"parameters={subtask.parameters}, prompt={subtask.prompt}")
                if not subtask.description or not subtask.parameters.get("language") or not subtask.parameters.get("output_files"):
                    self.log_update(f"Skipping invalid subtask {subtask_id}: missing required fields")
                    continue
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
                            parameters={**subtask.parameters, **params},
                            dependencies=subtask.dependencies,
                            prompt=subtask.prompt  # Pass prompt
                        )
                        self.log_update(f"Executing {next_agent_name} for subtask {subtask_id} with params: {new_task.parameters}, prompt: {new_task.prompt}")
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
                    new_task = Task(
                        task_id=task_id,
                        description=task.description,
                        parameters=params,
                        dependencies=task.dependencies,
                        prompt=task.prompt
                    )
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
                if any(dep_name.startswith("Architect_") and agent_outputs.get(dep_name, {}).get("status") == condition.get("status")
                       for dep_name, condition in deps):
                    self.log_update(f"Forcing execution of {next_agent_name} as Architect dependency met")
                    deps_satisfied = True
                else:
                    self.log_update(f"Dependencies not satisfied for {next_agent_name}, skipping")
                    continue
            agent = self.agents[next_agent_name]
            new_task = Task(
                task_id=task_id,
                description=task.description,
                parameters=agent_outputs,
                dependencies=task.dependencies,
                prompt=task.prompt
            )
            self.log_update(f"Executing agent {next_agent_name} with params: {new_task.parameters}, prompt: {new_task.prompt}")
            try:
                start_time = time.time()
                agent_status, agent_result = agent.process_task(new_task)
                elapsed = time.time() - start_time
                self.log_update(f"Agent {next_agent_name} returned status={agent_status}, result_type={type(agent_result).__name__}, time={elapsed:.2f}s")
                agent.track_flow(new_task, agent_status, agent_result, new_task.parameters.get("use_remote", False))
                self.tasks[task_id]["processed"].add(next_agent_name)
                self.tasks[task_id]["outputs"][next_agent_name] = {"status": agent_status, "result": agent_result}
                task.parameters[next_agent_name] = {"status": agent_status, "result": agent_result}
                final_status, final_result = self._propagate(next_agent_name, agent_status, agent_result, task, stop_at)
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
    satisfied_agents = []
    for agent_name in pending_agents:
        deps = self.graph.get(agent_name, [])
        agent_outputs = self.tasks.get(task_id, {}).get("outputs", {})
        deps_satisfied = all(
            dep_name in agent_outputs and
            self._check_condition(agent_outputs[dep_name]["status"], agent_outputs[dep_name]["result"], condition)
            for dep_name, condition in deps
        )
        if deps_satisfied:
            satisfied_agents.append(agent_name)
            self.log_update(f"Agent {agent_name} has satisfied dependencies: {deps}")

    if satisfied_agents:
        selected_agent = satisfied_agents[0]  # Select first agent with satisfied dependencies
        self.log_update(f"Selected agent {selected_agent} with satisfied dependencies")
        return selected_agent

    self.log_update(f"No agent with satisfied dependencies, checking Architect dependencies")
    # Check if any Architect dependencies are met
    for agent_name in pending_agents:
        deps = self.graph.get(agent_name, [])
        agent_outputs = self.tasks.get(task_id, {}).get("outputs", {})
        if any(dep_name.startswith("Architect_") and agent_outputs.get(dep_name, {}).get("status") == condition.get("status")
               for dep_name, condition in deps):
            self.log_update(f"Selected agent {agent_name} due to Architect dependency")
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
            f"Task prompt: {task.prompt}\n"
            "Which agent should process the task next? Return only the agent name or 'None' if no step is clear."
        )
        decision = self.infer(prompt, task).strip()
        elapsed = time.time() - start_time
        self.log_update(f"Inference decided next step: {decision}, time={elapsed:.2f}s")
        for agent_name in pending_agents:
            if agent_name in decision:
                self.log_update(f"Matched agent {agent_name} in decision")
                return agent_name
        return None
    except Exception as e:
        self.log_update(f"Error in decide_next_step inference: {str(e)}")
        return None
