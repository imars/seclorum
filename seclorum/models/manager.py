# seclorum/models/manager.py
from abc import ABC, abstractmethod
from typing import Optional
import subprocess
import time
import logging
import ollama

logger = logging.getLogger("ModelManager")

class ModelManager(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text based on the given prompt with optional parameters."""
        pass

    def __init__(self, model_name: str):
        self.model_name = model_name

class OllamaModelManager(ModelManager):
    def __init__(self, model_name: str = "codellama", host: Optional[str] = None):
        super().__init__(model_name)
        self.host = host or "http://localhost:11434"
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
            response = self.client.generate(model=self.model_name, prompt=prompt, **kwargs)
            return response['response'].strip()
        except Exception as e:
            logger.error(f"Failed to generate with {self.model_name}: {str(e)}")
            raise

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):  # Already correct, but verify
        super().__init__(model_name)  # Ensure model_name is set via base class

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
