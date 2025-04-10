# seclorum/agents/remote.py
import requests
from typing import Optional, Dict, Any
import os
import logging
import time

class Remote:
    """Mixin to provide optional remote inference capabilities to agents."""
    REMOTE_ENDPOINTS = {
        "google_ai_studio": {
            "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            "api_key": None,
            "model": "gemini-2.0-flash",
            "headers": {"Content-Type": "application/json"}
        }
    }

    _last_remote_call = 0
    _remote_call_count = 0
    _rate_limit_window = 60
    _max_calls_per_window = 10

    def remote_infer(self, prompt: str, endpoint: str = "google_ai_studio", **kwargs) -> Optional[str]:
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))

        endpoint_config = self.REMOTE_ENDPOINTS.get(endpoint)
        if not endpoint_config:
            logger.warning(f"Unknown remote endpoint: {endpoint}")
            return None

        api_key = endpoint_config["api_key"] or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            logger.warning(f"No API key configured for {endpoint}")
            return None

        # Updated payload to match Gemini API
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                **{k: v for k, v in kwargs.items() if k in ["topP", "topK"]}
            }
        }
        headers = endpoint_config["headers"].copy()
        headers["Authorization"] = f"Bearer {api_key}"  # Not needed for Gemini API with ?key=

        # Use query param for API key as per Gemini API convention
        url = f"{endpoint_config['url']}?key={api_key}"

        logger.debug(f"Sending inference request to {endpoint}")
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            # Adjust response parsing for Gemini API
            result = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            logger.debug(f"Remote inference successful: {result[:50]}...")
            current_time = time.time()
            if current_time - self._last_remote_call > self._rate_limit_window:
                self._remote_call_count = 0
            self._remote_call_count += 1
            self._last_remote_call = current_time
            return result.strip()
        except requests.RequestException as e:
            logger.error(f"Remote inference failed: {str(e)}")
            return None

    def should_use_remote(self, prompt: str) -> bool:
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))
        has_local_model = hasattr(self, "model") and self.model is not None
        prompt_length = len(prompt)
        is_complex = prompt_length > 200
        current_time = time.time()
        if current_time - self._last_remote_call > self._rate_limit_window:
            self._remote_call_count = 0
        rate_limit_ok = self._remote_call_count < self._max_calls_per_window

        if not has_local_model:
            logger.debug("No local model, preferring remote")
            return rate_limit_ok
        if is_complex:
            logger.debug("Complex prompt, considering remote")
            return rate_limit_ok
        if rate_limit_ok and prompt_length > 50:
            logger.debug("Rate limit allows, using remote for moderate prompt")
            return True
        logger.debug("Defaulting to local inference")
        return False

    def generate(self, prompt: str, use_remote: Optional[bool] = None, endpoint: str = "google_ai_studio", **kwargs) -> str:
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))
        should_use_remote = use_remote if use_remote is not None else self.should_use_remote(prompt)

        if should_use_remote:
            result = self.remote_infer(prompt, endpoint, **kwargs)
            if result is not None:
                return result
            logger.warning("Remote inference failed, falling back to local model")

        if hasattr(self, "model") and self.model:
            return self.model.generate(prompt, **kwargs)
        raise RuntimeError("No local model available and remote inference failed")

    def set_remote_endpoint(self, endpoint: str, config: Dict[str, Any]):
        self.REMOTE_ENDPOINTS[endpoint] = config
