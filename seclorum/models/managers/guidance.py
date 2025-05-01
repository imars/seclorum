# seclorum/models/managers/guidance.py
from typing import Optional
import logging
import os
import json
import guidance
from ..manager import ModelManager

try:
    from guidance.models import LlamaCpp as GuidanceLlamaCpp
except ImportError as e:
    logging.warning(f"Failed to import guidance: {str(e)}. Guidance support will be disabled.")
    guidance = None
    GuidanceLlamaCpp = None

logger = logging.getLogger("ModelManager")

class GuidanceModelManager(ModelManager):
    def __init__(self, model_name: str = "llama3.2"):
        super().__init__(model_name, provider="guidance")
        if not guidance or not GuidanceLlamaCpp:
            raise ImportError("Guidance dependencies not available. Install with `pip install guidance`")
        model_path = self._get_model_path(model_name)
        if not model_path:
            raise ValueError(f"No GGUF file found for model {model_name}")
        self.logger.info(f"Loading GGUF model with Guidance from {model_path} for {model_name}")
        try:
            # Set LLAMA_CPP_MODEL temporarily to avoid model_path conflict
            original_env = os.environ.get("LLAMA_CPP_MODEL")
            os.environ["LLAMA_CPP_MODEL"] = model_path
            self.logger.debug(f"Set LLAMA_CPP_MODEL to {model_path}")
            self.llm = GuidanceLlamaCpp(n_ctx=16384, verbose=True, chat_template=None)
            self.logger.info(f"Guidance model initialized for {model_name}")
            # Restore original environment variable
            if original_env is None:
                os.environ.pop("LLAMA_CPP_MODEL", None)
            else:
                os.environ["LLAMA_CPP_MODEL"] = original_env
        except Exception as e:
            self.logger.error(f"Failed to initialize Guidance model for {model_name}: {str(e)}")
            raise

    def _get_model_path(self, model_name: str) -> Optional[str]:
        ollama_model_dir = os.path.expanduser("~/.ollama/models")
        manifest_base = os.path.join(ollama_model_dir, "manifests", "registry.ollama.ai", "library")
        manifest_map = {
            "llama3.2:latest": os.path.join(manifest_base, "llama3.2", "latest"),
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

            self.logger.info(f"Generating with Guidance for {self.model_name}, schema: {schema is not None}")
            # Set the default model for guidance
            guidance.llm = self.llm

            if not schema or not callable(schema):
                self.logger.warning("No valid schema provided for Guidance generation. Falling back to standard prompt.")
                system = kwargs.get("system", "Output only valid JSON. Do not include markdown, comments, or additional text.")
                prompt = f"{system}\n\n{prompt}"
                result = self.llm(prompt, max_tokens=max_tokens, temperature=temperature)
                result_str = str(result).strip()
                try:
                    json.loads(result_str)
                    self.logger.debug(f"Guidance output validated: {result_str[:200]}...")
                except json.JSONDecodeError:
                    self.logger.warning("Guidance output is not valid JSON. Returning raw output.")
                    result_str = json.dumps({"error": "Invalid JSON output", "raw": result_str})
                return result_str

            # Execute the provided schema (a @guidance-decorated function)
            result = schema()  # Call the schema function
            result_json = json.dumps(result.variables)  # Access variables from the Program object
            self.logger.debug(f"Guidance structured output: {result_json[:200]}...")
            return result_json
        except Exception as e:
            self.logger.error(f"Failed to generate with Guidance for {self.model_name}: {str(e)}")
            return json.dumps({"error": "Generation failed", "raw": str(e)})
