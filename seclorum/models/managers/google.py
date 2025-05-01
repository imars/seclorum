# seclorum/models/model_managers/google.py
import logging
import os
import requests
from ..manager import ModelManager
from ...agents.settings import Settings

logger = logging.getLogger("ModelManager")

class GoogleModelManager(ModelManager):
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        super().__init__(model_name, provider="google_ai_studio")
        self.api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not self.api_key:
            self.logger.warning("GOOGLE_AI_STUDIO_API_KEY not set, structured output may be limited")

    def generate(self, prompt: str, **kwargs) -> str:
        if not self.api_key:
            self.logger.error("GOOGLE_AI_STUDIO_API_KEY not set. Set it with 'export GOOGLE_AI_STUDIO_API_KEY=your_key'")
            return ""

        max_tokens = kwargs.get("max_tokens", Settings.Agent.RemoteInfer.MAX_TOKENS_DEFAULT)
        temperature = kwargs.get("temperature", Settings.Agent.RemoteInfer.TEMPERATURE_DEFAULT)
        function_call = kwargs.get("function_call", None)

        if function_call:
            schema = function_call.get("schema")
            self.logger.info(f"Using responseSchema for JSON generation with schema for {self.model_name}")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                    "responseMimeType": "application/json",
                    "responseSchema": schema
                }
            }
            try:
                response = requests.post(
                    f"{url}?key={self.api_key}",
                    json=data,
                    headers=headers,
                    timeout=kwargs.get("timeout", Settings.Agent.RemoteInfer.TIMEOUT_DEFAULT)
                )
                response.raise_for_status()
                result = response.json()
                if not result.get("candidates"):
                    self.logger.error("Remote inference returned no candidates")
                    return ""
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                if not text.strip():
                    self.logger.error("Remote inference returned empty text")
                    return ""
                self.logger.debug(f"responseSchema output: {text[:200]}...")
                return text.strip()
            except Exception as e:
                self.logger.warning(f"responseSchema generation failed: {str(e)}. Falling back to standard generation.")

        self.logger.info(f"Using standard generation for {self.model_name}")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }
        try:
            response = requests.post(
                f"{url}?key={self.api_key}",
                json=data,
                headers=headers,
                timeout=kwargs.get("timeout", Settings.Agent.RemoteInfer.TIMEOUT_DEFAULT)
            )
            response.raise_for_status()
            result = response.json()
            if not result.get("candidates"):
                self.logger.error("Remote inference returned no candidates")
                return ""
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            if not text.strip():
                self.logger.error("Remote inference returned empty text")
                return ""
            self.logger.debug(f"Standard generation output: {text[:200]}...")
            return text.strip()
        except Exception as e:
            self.logger.error(f"Remote inference failed: {str(e)}")
            return ""
