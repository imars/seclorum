# seclorum/models/managers/transformers.py
from typing import Optional
import logging
import json
from pydantic import BaseModel
import outlines
import outlines.models
from transformers import AutoModelForCausalLM, AutoTokenizer
from ..manager import ModelManager
from ..plan import Plan

logger = logging.getLogger("ModelManager")

class TransformersModelManager(ModelManager):
    def __init__(self, model_name: str = "distilgpt2"):
        super().__init__(model_name, provider="transformers")
        self.logger.debug(f"Attempting to load Transformers model {model_name}")
        self.model = None
        self.tokenizer = None
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model = AutoModelForCausalLM.from_pretrained(model_name)
            self.outlines_model = outlines.models.transformers(self.model, self.tokenizer)
            self.logger.info(f"Transformers model initialized for {model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Transformers model for {model_name}: {str(e)}")
            raise ValueError(f"Failed to load model {model_name}: {str(e)}. Ensure the model is available on Hugging Face and compatible with your setup.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if hasattr(self, 'model') and self.model is not None:
            del self.model
            self.model = None
            self.logger.debug("Cleared Transformers model")
        if hasattr(self, 'tokenizer') and self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
            self.logger.debug("Cleared Transformers tokenizer")

    def __del__(self):
        self.close()

    def generate(self, prompt: str, **kwargs) -> str:
        try:
            max_tokens = kwargs.get("max_tokens", 4096)
            temperature = kwargs.get("temperature", 0.7)
            top_k = kwargs.get("top_k", 40)
            function_call = kwargs.get("function_call", None)
            schema = function_call.get("schema") if function_call else None

            self.logger.info(f"Generating with Transformers for {self.model_name}, schema: {schema is not None}")
            if not schema:
                system = kwargs.get("system", "You are a helpful assistant. Output only the exact response requested, with no explanations, code, programming instructions, or extra content.")
                prompt_formatted = f"{system}\n\n{prompt}"
                generator = outlines.generate.text(self.outlines_model)
                result = generator(prompt_formatted, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
                result_str = str(result).strip()
                self.logger.debug(f"Transformers text output: {result_str[:200]}...")
                return result_str

            # JSON generation with schema
            system = kwargs.get("system", "You are a helpful assistant. Generate valid JSON output according to the provided schema, with no extra text, reasoning, or dialogue.")
            prompt_formatted = f"{system}\n\n{prompt}"
            generator = outlines.generate.json(self.outlines_model, schema)
            result = generator(prompt_formatted, max_tokens=max_tokens, temperature=temperature, top_k=top_k)
            result_dict = result.dict() if isinstance(result, BaseModel) else result

            # Post-process JSON output
            def clean_dict(d):
                if isinstance(d, dict):
                    return {k: clean_dict(v) for k, v in d.items()}
                elif isinstance(d, list):
                    return [clean_dict(v) for v in d]
                elif isinstance(d, str):
                    return ''.join(c for c in d if ord(c) < 128 and c.isprintable())  # ASCII-only
                return d

            cleaned_dict = clean_dict(result_dict)
            result_json = json.dumps(cleaned_dict, ensure_ascii=True)
            self.logger.debug(f"Transformers structured output: {result_json[:200]}...")
            Plan.model_validate_json(result_json)
            return result_json

        except Exception as e:
            self.logger.error(f"Failed to generate with Transformers for {self.model_name}: {str(e)}")
            return json.dumps({"error": "Generation failed", "raw": str(e)})
