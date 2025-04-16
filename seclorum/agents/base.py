# seclorum/agents/base.py
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

    @timeout_decorator.timeout(1200, timeout_exception=TimeoutError)
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

