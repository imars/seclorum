# seclorum/models/managers/llama_cpp.py
from typing import Optional
import logging
import os
import json
import re
from ..manager import ModelManager
from .chat_template import CustomChatTemplate

try:
    from llama_cpp import Llama, llama_chat_apply_template
except ImportError as e:
    logging.error(f"Failed to import llama_cpp: {str(e)}. Install with `pip install llama_cpp_python`.")
    Llama = None
    llama_chat_apply_template = None

logger = logging.getLogger("ModelManager")

class LlamaCppModelManager(ModelManager):
    def __init__(self, model_name: str = "llama3.2"):
        super().__init__(model_name, provider="llama_cpp")
        self.llama_cpp = None
        if not Llama or not llama_chat_apply_template:
            raise ImportError("Required dependencies (llama_cpp, llama_chat_apply_template) not available. Install with `pip install llama_cpp_python`")
        model_path = self._get_model_path(model_name)
        if not model_path:
            raise ValueError(f"No GGUF file found for model {model_name}")
        try:
            self.logger.info(f"Loading GGUF model from {model_path} for {model_name}")
            self.llama_cpp = Llama(model_path=model_path, n_ctx=16384, verbose=True)
            self.chat_template = CustomChatTemplate(model_name)
            self.logger.info(f"LlamaCpp model initialized for {model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize LlamaCpp model for {model_name}: {str(e)}")
            raise

    def _get_model_path(self, model_name: str) -> Optional[str]:
        """Locate GGUF file for the given model using ModelManager's method."""
        return super()._get_model_path(model_name)

    def _extract_json(self, raw_output: str) -> str:
        raw_output = re.sub(r'```(?:json)?\n([\s\S]*?)\n```', r'\1', raw_output)
        json_match = re.search(r'\{[\s\S]*\}', raw_output)
        if not json_match:
            return raw_output
        json_str = json_match.group(0)
        try:
            parsed = json.loads(json_str)
            return json.dumps(parsed)
        except json.JSONDecodeError:
            return json_str.strip()

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            max_tokens = kwargs.get("max_tokens", 4096)
            temperature = kwargs.get("temperature", 0.3)
            messages = kwargs.get("messages", None)
            system = kwargs.get("system", "Output only valid JSON. Do not include markdown, comments, or additional text.")
            function_call = kwargs.get("function_call", None)
            tools = function_call.get("tools") if function_call else None

            if not self.llama_cpp:
                raise ValueError("llama_cpp model not initialized")

            if messages:
                try:
                    prompt = self.chat_template.apply_chat_template(messages, system=system, tools=tools)
                except Exception as e:
                    logger.warning(f"Chat template failed: {str(e)}. Using raw prompt.")
                    prompt = f"{system}\n\n{prompt}"
            else:
                prompt = f"{system}\n\n{prompt}"

            logger.info(f"Using standard generation for {self.model_name} with max_tokens={max_tokens}, temperature={temperature}")
            output = self.llama_cpp(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=["</s>", "<|eot_id|>", "\n\n"],
                top_p=0.9,
                top_k=40
            )
            raw_result = output["choices"][0]["text"].strip()
            result = self._extract_json(raw_result)
            if function_call:
                try:
                    json.loads(result)
                    logger.debug(f"JSON output validated: {result[:200]}...")
                except json.JSONDecodeError as e:
                    logger.warning(f"Output is not valid JSON: {str(e)}. Returning raw output.")
                    result = json.dumps({"error": "Invalid JSON output", "raw": raw_result})
            logger.debug(f"Standard generation output: {result[:200]}...")
            return result
        except Exception as e:
            logger.error(f"Failed to generate with {self.model_name}: {str(e)}")
            return json.dumps({"error": "Generation failed", "raw": str(e)})
