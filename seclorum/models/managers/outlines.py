# seclorum/models/managers/outlines.py
from typing import Optional
import logging
import os
import json
from pydantic import BaseModel
import outlines
import outlines.models
import llama_cpp
from ..manager import ModelManager
from ..plan import Plan

try:
    from outlines.models import LlamaCpp as OutlinesLlamaCpp
except ImportError as e:
    logging.warning(f"Failed to import outlines: {str(e)}. Outlines support will be disabled.")
    outlines = None
    OutlinesLlamaCpp = None

logger = logging.getLogger("ModelManager")

class OutlinesModelManager(ModelManager):
    def __init__(self, model_name: str = "mistral:latest"):
        super().__init__(model_name, provider="outlines")
        if not outlines or not OutlinesLlamaCpp:
            raise ImportError("Outlines dependencies not available. Install with `pip install outlines`")
        model_path = self._get_model_path(model_name)
        if not model_path:
            raise ValueError(f"No GGUF file found for model {model_name}")
        self.logger.info(f"Loading GGUF model with Outlines from {model_path} for {model_name}")
        self.llama = None
        try:
            original_env = os.environ.get("LLAMA_CPP_MODEL")
            os.environ["LLAMA_CPP_MODEL"] = model_path
            self.logger.debug(f"Set LLAMA_CPP_MODEL to {model_path}")
            self.llama = llama_cpp.Llama(
                model_path=model_path,
                n_ctx=2048,
                verbose=True,
                n_gpu_layers=0
            )
            self.model = OutlinesLlamaCpp(model=self.llama)
            self.logger.info(f"Outlines model initialized for {model_name}")
            if original_env is None:
                os.environ.pop("LLAMA_CPP_MODEL", None)
            else:
                os.environ["LLAMA_CPP_MODEL"] = original_env
        except Exception as e:
            self.logger.error(f"Failed to initialize Outlines model for {model_name}: {str(e)}")
            if self.llama:
                self.llama.close()
            raise

    def close(self):
        """Close the Llama instance and release resources."""
        if hasattr(self, 'llama') and self.llama:
            try:
                self.llama.close()
                self.logger.debug("Closed llama_cpp.Llama instance")
                self.llama = None  # Prevent re-closing
            except Exception as e:
                self.logger.warning(f"Error closing llama_cpp.Llama: {str(e)}")
                raise

    def __del__(self):
        self.close()  # Reuse close method for cleanup

    def _get_model_path(self, model_name: str) -> Optional[str]:
        ollama_model_dir = os.path.expanduser("~/.ollama/models")
        manifest_base = os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "library")
        manifest_map = {
            "llama3.2:latest": os.path.join(manifest_base, "llama3.2", "latest"),
            "llama3.2:8b": os.path.join(manifest_base, "llama3.2", "8b"),
            "mistral:latest": os.path.join(manifest_base, "mistral", "latest"),
            "deepseek-r1:8b": os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "deepseek", "deepseek-r1", "8b"),
            "deepseek-r1:latest": os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "deepseek", "deepseek-r1", "latest"),
            "codellama:7b-instruct": os.path.join(manifest_base, "codellama", "7b-instruct"),
        }
        manifest_path = manifest_map.get(model_name)
        if not manifest_path or not os.path.exists(manifest_path):
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
                            if os.path.exists(file_path):
                                self.logger.info(f"Found GGUF file for {model_name}: {file_path}")
                                return file_path
                self.logger.warning(f"No valid GGUF file found in manifest for {model_name}")
                return None
        except Exception as e:
            self.logger.error(f"Failed to read manifest for {model_name}: {str(e)}")
            return None

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            max_tokens = kwargs.get("max_tokens", 4096)
            temperature = kwargs.get("temperature", 0.3)
            function_call = kwargs.get("function_call", None)
            schema = function_call.get("schema") if function_call else None

            self.logger.info(f"Generating with Outlines for {self.model_name}, schema: {schema is not None}")
            if not schema:
                self.logger.warning("No schema provided for Outlines generation. Falling back to standard prompt.")
                system = kwargs.get("system", "Output only valid JSON. Do not include markdown, comments, or additional text.")
                prompt = f"{system}\n\n{prompt}"
                generator = outlines.generate.text(self.model)
                result = generator(prompt, max_tokens=max_tokens, temperature=temperature)
                result_str = str(result).strip()
                try:
                    json.loads(result_str)
                    self.logger.debug(f"Outlines output validated: {result_str[:200]}...")
                except json.JSONDecodeError:
                    self.logger.warning("Outlines output is not valid JSON. Returning raw output.")
                    result_str = json.dumps({"error": "Invalid JSON output", "raw": result_str})
                return result_str

            generator = outlines.generate.json(self.model, schema)
            result = generator(prompt, max_tokens=max_tokens, temperature=temperature)
            # Serialize Pydantic model to dict for JSON compatibility
            result_dict = result.dict() if isinstance(result, BaseModel) else result
            result_json = json.dumps(result_dict)
            self.logger.debug(f"Outlines structured output: {result_json[:200]}...")
            return result_json
        except Exception as e:
            self.logger.error(f"Failed to generate with Outlines for {self.model_name}: {str(e)}")
            return json.dumps({"error": "Generation failed", "raw": str(e)})
