# seclorum/models/manager.py
from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import time
import logging
import httpx
import ollama

logger = logging.getLogger("ModelManager")

class ModelManager(ABC):
    _model_cache = {}  # Class-level cache for models

    def __init__(self, model_name: str, provider: str = "ollama", host: str = "http://localhost:11434"):
        self.logger = logging.getLogger(f"ModelManager")
        self.model_name = model_name
        self.provider = provider
        self.host = host

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

    @classmethod
    def get_or_create(cls, model_name: str, provider: str = "ollama", host: str = "http://localhost:11434") -> 'ModelManager':
        key = (model_name, provider, host)
        if key not in cls._model_cache:
            if provider.lower() == "ollama":
                cls._model_cache[key] = OllamaModelManager(model_name, host)
            elif provider.lower() == "mock":
                cls._model_cache[key] = MockModelManager(model_name)
            else:
                raise ValueError(f"Unknown model provider: {provider}")
        return cls._model_cache[key]

class OllamaModelManager(ModelManager):
    def __init__(self, model_name: str = "codellama", host: Optional[str] = None):
        super().__init__(model_name, provider="ollama", host=host or "http://localhost:11434")
        self.client = ollama.Client(host=self.host)
        self.ensure_model_and_server()

    def ensure_model_and_server(self):
        try:
            response = self.client.list()
            self.logger.info(f"Ollama server running at {self.host}")
            models = response.get('models', [])
            model_key = 'model'
            if not any(m.get(model_key) == f"{self.model_name}:latest" for m in models):
                self.logger.info(f"Model {self.model_name} not found. Pulling it...")
                subprocess.run(["ollama", "pull", self.model_name], check=True)
                self.logger.info(f"Model {self.model_name} pulled successfully")
            else:
                self.logger.info(f"Model {self.model_name} already available")
        except Exception as e:
            self.logger.warning(f"Ollama server not running or model check failed: {str(e)}. Starting server...")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)
            self.ensure_model_and_server()  # Retry after starting server

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            valid_kwargs = {k: v for k, v in kwargs.items() if k in ['system', 'template', 'context']}
            response = self.client.generate(model=self.model_name, prompt=prompt, **valid_kwargs)
            return response['response'].strip()
        except Exception as e:
            self.logger.error(f"Failed to generate with {self.model_name}: {str(e)}")
            raise

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name, provider="mock")

    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]"
        elif "Generate a Python unit test" in prompt:
            return "import unittest\ndef test_list_files():\n    files = [f for f in os.listdir('.') if f.endswith('.py')]\n    assert isinstance(files, list)"
        return "Mock response"

def create_model_manager(provider: str = "ollama", model_name: str = "llama3.2:latest", **kwargs) -> ModelManager:
    return ModelManager.get_or_create(model_name, provider, kwargs.get("host", "http://localhost:11434"))
