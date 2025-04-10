# seclorum/models/manager.py
from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import time
import logging
import ollama

logger = logging.getLogger("ModelManager")

class ModelManager(ABC):
    def __init__(self, model_name: str, provider: str = "ollama", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.provider = provider
        self.base_url = base_url
        self.logger = logging.getLogger(f"ModelManager_{model_name}")

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

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
