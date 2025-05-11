# seclorum/models/manager.py
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging
import os
import json
from pathlib import Path

logger = logging.getLogger("ModelManager")

class ModelManager(ABC):
    _model_cache = {}
    _model_path_cache = {}  # Cache for model name to manifest path

    def __init__(self, model_name: str, provider: str, host: Optional[str] = None):
        self.logger = logging.getLogger("ModelManager")
        self.model_name = model_name
        self.provider = provider
        self.host = host

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        pass

    def close(self):
        """Optional method for resource cleanup."""
        pass

    def _build_model_path_cache(self) -> Dict[str, str]:
        """Scan Ollama model directory to build a model-to-manifest-path map."""
        if self._model_path_cache:
            self.logger.debug("Using cached model path map")
            return self._model_path_cache

        ollama_model_dir = os.path.expanduser("~/.ollama/models")
        manifest_base = os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "library")
        self.logger.debug(f"Scanning manifest directory: {manifest_base}")

        if not os.path.exists(manifest_base):
            self.logger.warning(f"Ollama manifest directory not found: {manifest_base}")
            return {}

        model_map = {}
        try:
            # Walk the library directory to find manifest files
            for root, _, files in os.walk(manifest_base):
                for file in files:
                    if file.endswith(".json") or file in ["latest", "7b", "8b"]:  # Manifest files or tags
                        # Extract model name and tag from path
                        rel_path = os.path.relpath(root, manifest_base)
                        model_parts = rel_path.split(os.sep)
                        if len(model_parts) == 1:  # e.g., llama3.2/latest
                            model_name = f"{model_parts[0]}:{file}"
                            manifest_path = os.path.join(root, file)
                            model_map[model_name] = manifest_path
                        elif len(model_parts) == 2:  # e.g., codellama/7b-instruct
                            model_name = f"{model_parts[0]}:{model_parts[1]}"
                            manifest_path = os.path.join(root, file)
                            model_map[model_name] = manifest_path

            self.logger.debug(f"Built model path map: {list(model_map.keys())}")
            self._model_path_cache = model_map
            return model_map
        except Exception as e:
            self.logger.error(f"Failed to build model path cache: {str(e)}")
            return {}

    def _get_model_path(self, model_name: str) -> Optional[str]:
        """Locate GGUF file for the given model in Ollama's model directory."""
        ollama_model_dir = os.path.expanduser("~/.ollama/models")
        model_map = self._build_model_path_cache()

        manifest_path = model_map.get(model_name)
        if not manifest_path:
            self.logger.warning(f"No manifest mapping for {model_name}")
            # Fallback: construct path dynamically
            model_parts = model_name.split(":")
            model_base = model_parts[0]
            tag = model_parts[1] if len(model_parts) > 1 else "latest"
            manifest_path = os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "library", model_base, tag)

        self.logger.debug(f"Checking manifest path: {manifest_path}")
        if not os.path.exists(manifest_path):
            self.logger.warning(f"No manifest file found for {model_name} at {manifest_path}")
            return None

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                self.logger.debug(f"Manifest for {model_name}: {json.dumps(manifest, indent=2)}")
                for layer in manifest.get("layers", []):
                    if layer.get("mediaType") == "application/vnd.ollama.image.model":
                        digest = layer.get("digest", "")
                        if digest.startswith("sha256:"):
                            file_name = f"sha256-{digest[7:]}"
                            file_path = os.path.join(ollama_model_dir, "blobs", file_name)
                            self.logger.debug(f"Checking GGUF file: {file_path}")
                            if os.path.exists(file_path):
                                self.logger.info(f"Found GGUF file for {model_name}: {file_path}")
                                return file_path
                            else:
                                self.logger.warning(f"GGUF file not found at {file_path}")
                self.logger.warning(f"No valid GGUF file found in manifest for {model_name}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to read manifest for {model_name}: {str(e)}")
            return None

    @classmethod
    def get_or_create(cls, model_name: str, provider: str = "outlines", host: Optional[str] = None) -> 'ModelManager':
        from .managers.ollama import OllamaModelManager
        from .managers.google import GoogleModelManager
        from .managers.mock import MockModelManager
        from .managers.outlines import OutlinesModelManager

        key = (model_name, provider, host or "")
        if key not in cls._model_cache:
            if provider.lower() == "ollama":
                cls._model_cache[key] = OllamaModelManager(model_name, host or "http://localhost:11434")
            elif provider.lower() == "outlines":
                cls._model_cache[key] = OutlinesModelManager(model_name)
            elif provider.lower() == "google_ai_studio":
                cls._model_cache[key] = GoogleModelManager(model_name)
            elif provider.lower() == "mock":
                cls._model_cache[key] = MockModelManager(model_name)
            else:
                raise ValueError(f"Unknown model provider: {provider}")
        return cls._model_cache[key]

def create_model_manager(provider: str = "outlines", model_name: str = "llama3.2:latest", **kwargs) -> ModelManager:
    return ModelManager.get_or_create(model_name, provider, kwargs.get("host"))
