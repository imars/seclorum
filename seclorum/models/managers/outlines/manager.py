# seclorum/models/managers/outlines/manager.py
from typing import Optional
import logging
import os
import json
import torch
import outlines
import outlines.models
import llama_cpp
import transformers
from pydantic import BaseModel
from ...manager import ModelManager
from ...plan import Plan
from ....agents.remote import Remote  # Corrected import
from .settings import (
    TOKENIZER_MAPPING, PROBLEMATIC_ARCHITECTURES, SUPPORTED_ARCHITECTURES,
    MIN_LLAMA_CPP_VERSION, MODEL_PARAMS, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE,
    DEFAULT_TOP_K, MAX_RETRIES, OUTLINES_CACHE_DIR
)
from .tokenizer import TokenizerManager
from .utils import format_prompt, clean_dict, strip_chat_tokens

try:
    from outlines.caching import clear_cache
except ImportError as e:
    logging.warning(f"Failed to import outlines caching: {str(e)}. Cache clearing disabled.")
    clear_cache = None

logger = logging.getLogger("ModelManager")

class OutlinesModelManager(ModelManager, Remote):
    def __init__(self, model_name: str = "llama3.2:latest", use_custom_tokenizer: bool = True):
        super().__init__(model_name, provider="outlines")
        self.logger.debug(f"Attempting to load model {model_name}")
        self.llama = None
        self.transformer_model = None
        self.tokenizer = None
        self.tokenizer_manager = None
        self.architecture = "unknown"

        # Set custom cache directory
        os.environ.setdefault("OUTLINES_CACHE_DIR", OUTLINES_CACHE_DIR)

        # Check if model is a Transformers model
        if model_name.startswith("transformers:"):
            self.architecture = "transformers"
            hf_model_name = model_name.replace("transformers:", "")
            self.logger.info(f"Loading Transformers model {hf_model_name}")
            try:
                self.tokenizer = transformers.AutoTokenizer.from_pretrained(hf_model_name)
                self.transformer_model = transformers.AutoModelForCausalLM.from_pretrained(
                    hf_model_name, torch_dtype=torch.float32, device_map="cpu"
                )
                self.model = outlines.models.Transformers(self.transformer_model, self.tokenizer)
                self.logger.info(f"Transformers model initialized for {hf_model_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize Transformers model {hf_model_name}: {str(e)}")
                raise ValueError(f"Failed to load Transformers model {hf_model_name}: {str(e)}")
        else:
            # GGUF model loading
            model_path = self._get_model_path(model_name)
            if not model_path:
                raise ValueError(f"No GGUF file found for model {model_name}")
            self.logger.info(f"Loading GGUF model with Outlines from {model_path} for {model_name}")
            try:
                original_env = os.environ.get("LLAMA_CPP_MODEL")
                os.environ["LLAMA_CPP_MODEL"] = model_path
                self.logger.debug(f"Set LLAMA_CPP_MODEL to {model_path}")

                # Check GGUF metadata for architecture
                try:
                    from gguf import GGUFReader
                    gguf_reader = GGUFReader(model_path)
                    metadata = gguf_reader.get_metadata()
                    self.architecture = metadata.get("general.architecture", "unknown")
                    self.logger.debug(f"GGUF metadata: {metadata}")
                    if self.architecture == "unknown":
                        self.architecture = self._infer_architecture(model_name)
                    if self.architecture not in SUPPORTED_ARCHITECTURES:
                        self.logger.error(
                            f"Unsupported model architecture '{self.architecture}' for {model_name}. "
                            f"Supported architectures: {', '.join(SUPPORTED_ARCHITECTURES)}."
                        )
                        raise ValueError(f"Unsupported model architecture: {self.architecture}")
                    if self.architecture in PROBLEMATIC_ARCHITECTURES:
                        try:
                            from llama_cpp import __version__ as llama_cpp_version
                            self.logger.debug(f"llama_cpp_python version: {llama_cpp_version}")
                            if llama_cpp_version < MIN_LLAMA_CPP_VERSION:
                                self.logger.error(
                                    f"{self.architecture} requires llama_cpp_python>={MIN_LLAMA_CPP_VERSION}, found {llama_cpp_version}. "
                                    f"Run `pip install llama_cpp_python>={MIN_LLAMA_CPP_VERSION} --upgrade`."
                                )
                                raise ValueError(f"Outdated llama_cpp_python for {self.architecture}")
                        except ImportError:
                            self.logger.warning("Cannot check llama_cpp_python version; assuming model is supported.")
                    self.logger.debug(f"Model architecture for {model_name}: {self.architecture}")
                except ImportError:
                    self.logger.warning("GGUFReader not available; falling back to model name inference.")
                    self.architecture = self._infer_architecture(model_name)
                except Exception as e:
                    self.logger.warning(f"Failed to check GGUF metadata for {model_name}: {str(e)}")
                    self.architecture = self._infer_architecture(model_name)

                self.llama = llama_cpp.Llama(
                    model_path=model_path,
                    n_ctx=8192,
                    verbose=True,
                    n_gpu_layers=0  # CPU-only
                )
                self.model = outlines.models.LlamaCpp(model=self.llama)
                self.tokenizer_manager = TokenizerManager(
                    architecture=self.architecture,
                    model_name=model_name,
                    use_custom_tokenizer=use_custom_tokenizer,
                    llama_instance=self.llama
                )
                self.logger.info(f"Outlines model initialized for {model_name}")
                if original_env is None:
                    os.environ.pop("LLAMA_CPP_MODEL", None)
                else:
                    os.environ["LLAMA_CPP_MODEL"] = original_env
            except Exception as e:
                self.logger.error(f"Failed to initialize Outlines model for {model_name}: {str(e)}")
                if self.llama:
                    self.llama.close()
                raise ValueError(f"Failed to load model {model_name}: {str(e)}")

    def _infer_architecture(self, model_name: str) -> str:
        """Infer architecture from model_name if GGUF metadata is unavailable."""
        model_name_lower = model_name.lower()
        if "qwen3" in model_name_lower:
            return "qwen3"
        elif "phi4" in model_name_lower:
            return "phi4"
        elif "llama" in model_name_lower:
            return "llama"
        elif "mistral" in model_name_lower:
            return "mistral"
        elif "deepseek" in model_name_lower:
            return "deepseek"
        self.logger.warning(f"Could not infer architecture for {model_name}; defaulting to 'unknown'")
        return "unknown"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def clear_cache(self):
        """Clear the Outlines cache to reset any corrupted state."""
        if clear_cache:
            try:
                clear_cache()
                self.logger.debug("Outlines cache cleared successfully")
            except Exception as e:
                self.logger.warning(f"Failed to clear Outlines cache: {str(e)}")
        else:
            self.logger.warning("Outlines cache clearing not available; ensure outlines is installed correctly")

    def close(self):
        """Clean up all resources."""
        try:
            if self.llama:
                try:
                    self.llama.close()
                    self.logger.debug("Closed llama_cpp.Llama instance")
                    self.llama = None
                except Exception as e:
                    self.logger.warning(f"Error closing llama_cpp.Llama: {str(e)}")
            if self.transformer_model:
                try:
                    del self.transformer_model
                    del self.tokenizer
                    torch.cuda.empty_cache()
                    self.logger.debug("Closed Transformers model")
                    self.transformer_model = None
                    self.tokenizer = None
                except Exception as e:
                    self.logger.warning(f"Error closing Transformers model: {str(e)}")
            if self.tokenizer_manager:
                try:
                    self.tokenizer_manager.close()
                    self.logger.debug("Closed tokenizer manager")
                    self.tokenizer_manager = None
                except Exception as e:
                    self.logger.warning(f"Error closing tokenizer manager: {str(e)}")
            self.clear_cache()
        except Exception as e:
            self.logger.error(f"Error in close method: {str(e)}")

    def __del__(self):
        self.close()

    def generate(self, prompt: str, use_remote: Optional[bool] = None, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Generate output using local or remote inference."""
        max_tokens = kwargs.get("max_tokens", DEFAULT_MAX_TOKENS)
        temperature = kwargs.get("temperature", DEFAULT_TEMPERATURE)
        top_k = kwargs.get("top_k", DEFAULT_TOP_K)
        function_call = kwargs.get("function_call", None)
        schema = function_call.get("schema") if function_call else None
        force_custom_tokenizer = kwargs.get("force_custom_tokenizer", False)

        # Apply model-specific parameters
        for model_key, params in MODEL_PARAMS.items():
            if model_key == self.model_name or model_key == self.architecture:
                if "max_tokens" in params:
                    max_tokens = min(max_tokens, params["max_tokens"])
                if "temperature" in params:
                    temperature = params["temperature"]
                if "top_k" in params:
                    top_k = params["top_k"]
                if "prompt_suffix" in params:
                    prompt += params["prompt_suffix"]
                self.logger.debug(f"Applied params for {model_key}: max_tokens={max_tokens}, temperature={temperature}, top_k={top_k}")
                break

        # Decide whether to use remote inference
        should_use_remote = use_remote if use_remote is not None else self.should_use_remote(prompt)
        if should_use_remote:
            self.logger.info(f"Attempting remote inference with endpoint {endpoint}")
            result = self.remote_infer(
                prompt,
                endpoint=endpoint,
                max_tokens=max_tokens,
                temperature=temperature,
                top_k=top_k
            )
            if result is not None:
                try:
                    if schema:
                        json.loads(result)  # Validate JSON
                        Plan.model_validate_json(result)
                    self.logger.debug(f"Remote inference output: {result[:200]}...")
                    return result
                except json.JSONDecodeError:
                    self.logger.warning("Remote inference output is not valid JSON, falling back to local")
                except Exception as e:
                    self.logger.warning(f"Remote inference validation failed: {str(e)}, falling back to local")
            self.logger.warning("Remote inference failed, falling back to local model")

        # Local inference
        self.logger.info(f"Generating with local Outlines for {self.model_name}, schema: {schema is not None}")
        for attempt in range(MAX_RETRIES):
            try:
                if not schema:
                    system = kwargs.get("system", "You are a helpful assistant. Output only the exact response requested, with no explanations, code, programming instructions, or extra content.")
                    prompt_formatted = format_prompt(system, prompt, self.architecture)
                    generator = outlines.generate.text(self.model)
                    result = generator(prompt_formatted, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
                    result_str = str(result).strip()
                    result_str = strip_chat_tokens(result_str)
                    try:
                        json.loads(result_str)
                        self.logger.debug(f"Outlines text output validated as JSON: {result_str[:200]}...")
                    except json.JSONDecodeError:
                        self.logger.debug(f"Outlines text output: {result_str[:200]}...")
                    return result_str

                # JSON generation with schema
                system = kwargs.get("system", "You are a helpful assistant. Generate valid JSON output according to the provided schema, with no extra text, reasoning, or dialogue.")
                prompt_formatted = format_prompt(system, prompt, self.architecture)
                if self.architecture == "transformers":
                    generator = outlines.generate.json(self.model, schema)
                    result = generator(prompt_formatted, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
                    result_dict = result.dict() if isinstance(result, BaseModel) else result
                else:
                    # GGUF JSON generation
                    raw_output = self.llama(
                        prompt=prompt_formatted,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_k=top_k,
                        echo=False
                    )
                    raw_text = raw_output['choices'][0]['text']
                    self.logger.debug(f"Raw text: {raw_text[:200]}...")
                    tokens = self.tokenizer_manager.tokenize(raw_text, force_custom_tokenizer=force_custom_tokenizer)
                    cleaned_text = self.tokenizer_manager.detokenize(tokens, force_custom_tokenizer=force_custom_tokenizer)
                    self.logger.debug(f"Cleaned text: {cleaned_text[:200]}...")
                    generator = outlines.generate.json(self.model, schema)
                    result = generator(prompt_formatted + cleaned_text, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
                    result_dict = result.dict() if isinstance(result, BaseModel) else result

                cleaned_dict = clean_dict(result_dict)
                result_json = json.dumps(cleaned_dict, ensure_ascii=True)
                self.logger.debug(f"Outlines structured output: {result_json[:200]}...")
                Plan.model_validate_json(result_json)
                return result_json

            except Exception as e:
                self.logger.warning(f"Generation attempt {attempt + 1} failed: {str(e)}")
                if "Cannot convert token" in str(e):
                    self.logger.debug(f"Retrying due to tokenization error with token ID {getattr(e, 'token_id', 'unknown')}")
                    self.clear_cache()
                    kwargs["force_custom_tokenizer"] = True
                    continue
                if attempt == MAX_RETRIES - 1:
                    self.logger.info(f"Falling back to text generation for {self.model_name}")
                    system = kwargs.get("system", "You are a helpful assistant. Output only the exact response requested, with no explanations, code, programming instructions, or extra content.")
                    prompt_formatted = format_prompt(system, prompt, self.architecture)
                    generator = outlines.generate.text(self.model)
                    result = generator(prompt_formatted, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
                    result_str = str(result).strip()
                    result_str = strip_chat_tokens(result_str)
                    self.logger.debug(f"Text fallback output: {result_str[:200]}...")
                    try:
                        result_dict = json.loads(result_str)
                        result_json = json.dumps(result_dict, ensure_ascii=True)
                        Plan.model_validate_json(result_json)
                        return result_json
                    except json.JSONDecodeError:
                        self.logger.warning("Text fallback output is not valid JSON, returning raw text")
                        return result_str
                raise

        self.logger.error(f"All {MAX_RETRIES} generation attempts failed for {self.model_name}")
        return json.dumps({"error": "Generation failed", "raw": "Max retries exceeded due to tokenization errors"})
