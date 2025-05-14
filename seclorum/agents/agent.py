# seclorum/agents/agent.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Set, Callable
from collections import defaultdict
from seclorum.models import Task, TestResult, CodeOutput, Plan
from seclorum.agents.base import AbstractAgent
from seclorum.utils.logger import LoggerMixin
from seclorum.models import ModelManager, create_model_manager
from seclorum.core.filesystem import FileSystemManager
from seclorum.agents.memory.manager import MemoryManager
from seclorum.agents.remote import Remote
from seclorum.agents.settings import Settings
import logging
import requests
import os
import time
import timeout_decorator
import json
import hashlib
import random

class Agent(AbstractAgent, Remote):
    def __init__(self, name: str, session_id: str, model_manager: Optional[ModelManager] = None, model_name: str = "gemini-1.5-flash", memory_kwargs: Optional[Dict] = None):
        super().__init__(name, session_id)
        self.logger = logging.getLogger(f"Agent_{name}")
        self.model = model_manager or create_model_manager(provider="google_ai_studio", model_name=model_name)
        self.available_models = {"default": self.model}
        self.current_model_key = "default"
        memory_kwargs = memory_kwargs or {}
        self.memory_manager = MemoryManager(**memory_kwargs)
        self.log_update(f"Agent {name} initialized with model {self.model.model_name}, provider {self.model.provider}, session_id={session_id}")

    def stop(self):
        for model_key, model in self.available_models.items():
            if hasattr(model, 'close'):
                try:
                    model.close()
                    self.log_update(f"Closed model {model_key}: {model.model_name}")
                except Exception as e:
                    self.log_update(f"Error closing model {model_key}: {str(e)}")
        try:
            self.memory_manager.stop()
            self.log_update(f"Stopped MemoryManager for session_id={self.session_id}")
        except Exception as e:
            self.log_update(f"Error stopping MemoryManager: {str(e)}")
        super().stop()

    @abstractmethod
    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_prompt(self, task: Task) -> str:
        pass

    @timeout_decorator.timeout(15, timeout_exception=TimeoutError)
    def remote_infer(self, prompt: str, endpoint: str = "google_ai_studio", **kwargs) -> str:
        self.log_update(f"Starting remote inference to {endpoint}")
        if endpoint != "google_ai_studio":
            raise ValueError(f"Only google_ai_studio supported, got {endpoint}")
        api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            self.log_update("GOOGLE_AI_STUDIO_API_KEY not set")
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY not set. Set it with 'export GOOGLE_AI_STUDIO_API_KEY=your_key'")
        if len(api_key) < 10:
            self.log_update("Invalid GOOGLE_AI_STUDIO_API_KEY length")
            raise ValueError("GOOGLE_AI_STUDIO_API_KEY appears invalid")
        self.log_update(f"API key set (length: {len(api_key)})")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        max_tokens = kwargs.get("max_tokens", Settings.Agent.RemoteInfer.MAX_TOKENS_DEFAULT)
        if "task" in kwargs and hasattr(kwargs["task"], "parameters") and "max_tokens" in kwargs["task"].parameters:
            max_tokens = kwargs["task"].parameters["max_tokens"]
        elif os.getenv("MAX_TOKENS"):
            max_tokens = int(os.getenv("MAX_TOKENS"))
        timeout = (5, 10)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": kwargs.get("temperature", Settings.Agent.RemoteInfer.TEMPERATURE_DEFAULT)
            }
        }
        try:
            with requests.Session() as session:
                self.log_update("Sending preflight request to verify API connectivity")
                preflight_url = "https://generativelanguage.googleapis.com/v1beta/models?key=" + api_key
                preflight_response = session.get(preflight_url, timeout=(3, 5))
                preflight_response.raise_for_status()
                self.log_update("Preflight request successful")
        except requests.RequestException as e:
            self.log_update(f"Preflight request failed: {str(e)}")
            raise ValueError(f"Cannot connect to Google AI Studio API: {str(e)}")
        try:
            with requests.Session() as session:
                self.log_update(f"Sending main request to {url} with max_tokens={max_tokens}, timeout={timeout}")
                response = session.post(
                    url,
                    json=payload,
                    timeout=timeout,
                    stream=False
                )
                self.log_update(f"Received response: status_code={response.status_code}")
                response.raise_for_status()
                result = response.json()
                if not result.get("candidates"):
                    self.log_update("Remote inference returned no candidates")
                    return ""
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                if not text.strip():
                    self.log_update("Remote inference returned empty text")
                    return ""
                self.log_update(f"Remote inference successful: {text[:50]}...")
                return text.strip()
        except requests.HTTPError as e:
            self.log_update(f"HTTP error: {str(e)}")
            if e.response and e.response.status_code == 429:
                max_attempts = 3
                total_backoff_time = 0
                max_backoff_time = 15
                for attempt in range(max_attempts):
                    wait_time = min((2 ** attempt) + (random.random() / 100), max_backoff_time - total_backoff_time)
                    if total_backoff_time + wait_time > max_backoff_time:
                        self.log_update(f"Total backoff time exceeded {max_backoff_time}s")
                        raise requests.HTTPError("429 Client Error: Too Many Requests after retries")
                    self.log_update(f"Rate limit hit (429), retrying in {wait_time:.2f}s (attempt {attempt + 1}/{max_attempts})")
                    time.sleep(wait_time)
                    total_backoff_time += wait_time
                    try:
                        with requests.Session() as session:
                            response = session.post(
                                url,
                                json=payload,
                                timeout=timeout,
                                stream=False
                            )
                            self.log_update(f"Retry received response: status_code={response.status_code}")
                            response.raise_for_status()
                            result = response.json()
                            if not result.get("candidates"):
                                self.log_update("Retry returned no candidates")
                                return ""
                            text = result["candidates"][0]["content"]["parts"][0]["text"]
                            if not text.strip():
                                self.log_update("Retry returned empty text")
                                return ""
                            self.log_update(f"Retry successful: {text[:50]}...")
                            return text.strip()
                    except requests.HTTPError as retry_e:
                        self.log_update(f"Retry attempt {attempt + 1} failed: {str(retry_e)}")
                        if retry_e.response.status_code != 429:
                            raise
                self.log_update(f"All {max_attempts} retry attempts failed for rate limit")
                raise requests.HTTPError("429 Client Error: Too Many Requests after retries")
            raise
        except requests.Timeout:
            self.log_update(f"Request timed out: connect_timeout={timeout[0]}s, read_timeout={timeout[1]}s")
            raise
        except requests.ConnectionError as e:
            self.log_update(f"Connection error: {str(e)}")
            raise
        except requests.RequestException as e:
            self.log_update(f"Request error: {str(e)}")
            raise

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
        if task.parameters.get("use_remote", False):
            self.log_update("Task requires remote model, using default")
            return
        prompt = (
            f"Given the task '{task.description}', available models: {list(self.available_models.keys())}, "
            "which model should be used? Return only the model key."
        )
        model_key = self.infer(prompt, task).strip()
        if model_key in self.available_models:
            self.switch_model(model_key)
        else:
            self.log_update(f"Model '{model_key}' not found, sticking with '{self.current_model_key}'")

    def infer(self, prompt: str, task: Task, use_remote: Optional[bool] = None, use_context: bool = False,
              validate_fn: Optional[Callable[[str], bool]] = None, max_retries: int = Settings.Agent.Infer.MAX_RETRIES, **kwargs) -> str:
        self.log_update(f"Inferring with model '{self.current_model_key}' (provider: {self.model.provider}) on prompt: {prompt[:50]}...")
        start_time = time.time()
        attempt = 0
        best_result = ""
        prompt_hash = hashlib.sha256(f"{prompt}:{task.task_id}:{self.name}".encode()).hexdigest()
        self.log_update(f"Checking cache for prompt_hash={prompt_hash}")
        cached_result = self.memory_manager.load_cached_response(prompt_hash, self.session_id)
        if cached_result:
            self.log_update(f"Returning cached response for prompt_hash={prompt_hash}, length={len(cached_result)}")
            return cached_result
        context = ""
        if use_context:
            self.log_update(f"Loading conversation history for task_id={task.task_id}, agent_name={self.name}")
            history = self.memory_manager.load_history(task_id=task.task_id, agent_name=self.name, session_id=self.session_id)
            self.log_update(f"Loaded history for task_id={task.task_id}, agent_name={self.name}, count={len(history)}")
            if history:
                context = "\n".join([f"Prompt: {h[0]}\nResponse: {h[1]}" for h in history])
                prompt = f"Previous conversation:\n{context}\n\nCurrent task:\n{prompt}"
        while attempt < max_retries:
            try:
                use_remote = task.parameters.get("use_remote", False) if use_remote is None else use_remote
                if use_remote:
                    result = self.remote_infer(prompt, endpoint="google_ai_studio", task=task, **kwargs)
                else:
                    max_tokens = kwargs.get("max_tokens", Settings.Agent.Infer.MAX_TOKENS_DEFAULT)
                    if "max_tokens" in task.parameters:
                        max_tokens = task.parameters["max_tokens"]
                    elif os.getenv("MAX_TOKENS"):
                        max_tokens = int(os.getenv("MAX_TOKENS"))
                    infer_kwargs = {k: v for k, v in kwargs.items() if k != "max_tokens"}
                    result = self.model.generate(prompt, max_tokens=max_tokens, **infer_kwargs)
                    self.log_update(f"Raw model output (attempt {attempt + 1}): {result[:200]}...")
                if not result:
                    self.log_update(f"Inference attempt {attempt + 1} returned empty result for task {task.task_id}")
                    attempt += 1
                    prompt = self.get_retry_prompt(prompt, "", None, False)
                    continue
                self.log_update(f"Saving inference result to memory and cache for task {task.task_id}")
                self.memory_manager.save(prompt, result, task.task_id, self.name, self.session_id)
                self.memory_manager.cache_response(prompt_hash, result, self.session_id)
                self.log_update(f"Saved inference attempt {attempt + 1} to memory and cache for task {task.task_id}")
                if validate_fn and not validate_fn(result):
                    self.log_update(f"Inference attempt {attempt + 1} failed validation for task {task.task_id}")
                    prompt = self.get_retry_prompt(prompt, result, None, False)
                    attempt += 1
                    best_result = result
                    continue
                self.log_update(f"Inference completed in {time.time() - start_time:.2f}s, result_length={len(result)}")
                return result.strip()
            except Exception as e:
                self.log_update(f"Inference attempt {attempt + 1} failed for task {task.task_id}: {str(e)}")
                prompt = self.get_retry_prompt(prompt, best_result, e, False)
                attempt += 1
                if not best_result:
                    best_result = f"Error: {str(e)}"
        self.log_update(f"All {max_retries} inference attempts failed for task {task.task_id}")
        return best_result

    def process_task(self, task: Task) -> Tuple[str, Any]:
        raise NotImplementedError("Subclasses must implement process_task")

    def store_output(self, task: Task, status: str, result: Any, prompt: Optional[str] = None):
        agent_key = f"{self.name}"
        task.parameters[agent_key] = {"status": status, "result": result}
        self.log_update(f"Stored output for {self.name}: status={status}, result_type={type(result).__name__}")
        if prompt and result:
            self.log_update(f"Saving output to Memory: task_id={task.task_id}, agent_name={self.name}")
            self.memory_manager.save(prompt, json.dumps(result) if isinstance(result, dict) else str(result), task.task_id, self.name, self.session_id)
            self.log_update(f"Saved plan to Memory: task_id={task.task_id}, agent_name={self.name}")
