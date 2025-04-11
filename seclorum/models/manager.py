# seclorum/models/manager.py
from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import time
import logging
import ollama

logger = logging.getLogger("ModelManager")

# seclorum/models/manager.py (partial update)
from typing import Optional
import logging
import httpx

class ModelManager:
    _model_cache = {}  # Class-level cache for models

    def __init__(self, model_name: str, provider: str = "ollama", host: str = "http://localhost:11434"):
        self.logger = logging.getLogger(f"ModelManager")
        self.model_name = model_name
        self.provider = provider
        self.host = host
        self.check_server()

    def check_server(self):
        try:
            response = httpx.get(f"{self.host}/api/tags")
            response.raise_for_status()
            self.logger.info(f"Ollama server running at {self.host}")
            if not self.check_model():
                self.pull_model()
        except httpx.RequestError as e:
            self.logger.error(f"Failed to connect to Ollama server: {e}")
            raise

    def check_model(self) -> bool:
        response = httpx.get(f"{self.host}/api/tags")
        models = response.json().get("models", [])
        model_exists = any(model["name"] == self.model_name for model in models)
        self.logger.info(f"Model {self.model_name} {'already available' if model_exists else 'not found'}")
        return model_exists

    def pull_model(self):
        self.logger.info(f"Model {self.model_name} not found. Pulling it...")
        # Pull logic (unchanged)
        self.logger.info(f"Model {self.model_name} pulled successfully")

    @classmethod
    def get_or_create(cls, model_name: str, provider: str = "ollama", host: str = "http://localhost:11434") -> 'ModelManager':
        key = (model_name, provider, host)
        if key not in cls._model_cache:
            cls._model_cache[key] = cls(model_name, provider, host)
        return cls._model_cache[key]

def create_model_manager(provider: str = "ollama", model_name: str = "llama3.2:latest") -> ModelManager:
    return ModelManager.get_or_create(model_name, provider)

class OllamaModelManager(ModelManager):
    def __init__(self, model_name: str = "codellama", host: Optional[str] = None):
        super().__init__(model_name, provider="ollama", base_url=host or "http://localhost:11434")
        self.host = self.base_url
        self.client = ollama.Client(host=self.host)
        self.ensure_model_and_server()

    def ensure_model_and_server(self):
        """Ensure the Ollama server is running and the model is pulled."""
        try:
            self.client.list()
            logger.info(f"Ollama server running at {self.host}")
        except Exception as e:
            logger.warning(f"Ollama server not running at {self.host}: {str(e)}. Starting it...")
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(2)

        try:
            response = self.client.list()
            logger.debug(f"Ollama list response: {response}")
            models = response.get('models', [])
            model_key = 'model'
            if not any(m.get(model_key) == f"{self.model_name}:latest" for m in models):
                logger.info(f"Model {self.model_name} not found. Pulling it...")
                subprocess.run(["ollama", "pull", self.model_name], check=True)
                logger.info(f"Model {self.model_name} pulled successfully")
            else:
                logger.info(f"Model {self.model_name} already available")
        except Exception as e:
            logger.error(f"Failed to ensure model {self.model_name}: {str(e)}")
            raise

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            # Filter kwargs to only those supported by Ollama
            valid_kwargs = {k: v for k, v in kwargs.items() if k in ['system', 'template', 'context']}
            response = self.client.generate(model=self.model_name, prompt=prompt, **valid_kwargs)
            return response['response'].strip()
        except Exception as e:
            logger.error(f"Failed to generate with {self.model_name}: {str(e)}")
            raise

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name, provider="mock")

    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]"
        elif "Generate a Python unit test" in prompt:
            return "import os\ndef test_list_files():\n    files = [f for f in os.listdir('.') if f.endswith('.py')]\n    assert isinstance(files, list)"
        return "Mock response"

def create_model_manager(provider: str = "mock", model_name: str = None, **kwargs) -> ModelManager:
    if provider.lower() == "ollama":
        return OllamaModelManager(model_name=model_name or "codellama", **kwargs)
    elif provider.lower() == "mock":
        return MockModelManager(model_name=model_name or "mock")
    else:
        raise ValueError(f"Unknown model provider: {provider}")
