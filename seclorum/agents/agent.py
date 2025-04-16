# seclorum/agents/agent.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput, Plan
from seclorum.agents.base import AbstractAgent
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
