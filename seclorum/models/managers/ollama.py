# seclorum/models/managers/ollama.py
from typing import Optional, Any
import subprocess
import time
import logging
import ollama
import numpy as np
from ..manager import ModelManager

logger = logging.getLogger("OllamaModelManager")

class OllamaModelManager(ModelManager):
    def __init__(self, model_name: str = "llama3.2", host: str = "http://localhost:11434"):
        super().__init__(model_name, provider="ollama", host=host)
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
            self.ensure_model_and_server()

    def generate(self, prompt: str, task: str = "text", **kwargs) -> Any:
        try:
            if task == "embedding":
                response = self.client.embeddings(model=self.model_name, prompt=prompt)
                embedding = response.get("embedding")
                if not embedding:
                    self.logger.error(f"No embedding returned for {self.model_name}")
                    return np.zeros(768)  # Default for nomic-embed-text
                self.logger.debug(f"Generated embedding for prompt: {prompt[:50]}..., length={len(embedding)}")
                return np.array(embedding)

            max_tokens = kwargs.get("max_tokens", 16384)
            temperature = kwargs.get("temperature", 0.7)
            raw_mode = kwargs.get("raw", False)
            function_call = kwargs.get("function_call", None)
            import json

            if function_call and "mistral" in self.model_name.lower():
                options = {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                    "raw": raw_mode
                }
                response = self.client.chat(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "Output only valid JSON matching the provided schema. Do not include markdown, comments, or additional text."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    tools=[{
                        "type": "function",
                        "function": {
                            "name": "generate_plan",
                            "description": "Generate a plan with subtasks",
                            "parameters": function_call["schema"]
                        }
                    }],
                    options=options
                )
                if response.get("message", {}).get("tool_calls"):
                    tool_call = response["message"]["tool_calls"][0]
                    if tool_call["function"]["name"] == "generate_plan":
                        result = json.dumps(tool_call["function"]["arguments"])
                        self.logger.debug(f"Mistral function call output: {result[:200]}...")
                        return result
                self.logger.warning("No valid function call result, falling back to standard generation.")

            self.logger.info(f"Using standard generation for {self.model_name}")
            options = {
                "num_predict": max_tokens,
                "temperature": temperature,
                "raw": raw_mode
            }
            response = self.client.generate(
                model=self.model_name,
                prompt=prompt,
                system="Output only valid JSON. Do not include markdown, comments, or additional text.",
                options=options,
                **{k: v for k, v in kwargs.items() if k in ['system', 'template', 'context']}
            )
            result = response['response'].strip()
            self.logger.debug(f"Standard generation output: {result[:200]}...")
            return result
        except Exception as e:
            self.logger.error(f"Failed to generate {task} with {self.model_name}: {str(e)}")
            return np.zeros(768) if task == "embedding" else ""

    def close(self):
        self.logger.debug(f"Closing OllamaModelManager for model: {self.model_name}")
