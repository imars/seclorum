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
            "url": "https://api.googleaistudio.com/v1/models/gemini:generate",  # Update with actual if different
            "api_key": None,
            "model": "gemini-1.5-flash",
            "headers": {"Content-Type": "application/json"}
        }
    }

    # Track remote usage (simple rate limiting)
    _last_remote_call = 0  # Timestamp of last call
    _remote_call_count = 0  # Calls in the last minute
    _rate_limit_window = 60  # Seconds (e.g., 1 minute)
    _max_calls_per_window = 10  # Arbitrary limit; adjust per API docs

    def remote_infer(self, prompt: str, endpoint: str = "google_ai_studio", **kwargs) -> Optional[str]:
        """Perform inference using a remote endpoint."""
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))

        endpoint_config = self.REMOTE_ENDPOINTS.get(endpoint)
        if not endpoint_config:
            logger.warning(f"Unknown remote endpoint: {endpoint}")
            return None

        api_key = endpoint_config["api_key"] or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        if not api_key:
            logger.warning(f"No API key configured for {endpoint}")
            return None

        payload = {
            "prompt": prompt,
            "model": endpoint_config["model"],
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            **kwargs
        }
        headers = endpoint_config["headers"].copy()
        headers["Authorization"] = f"Bearer {api_key}"

        logger.debug(f"Sending inference request to {endpoint}")
        try:
            response = requests.post(endpoint_config["url"], json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json().get("generated_text", "") or response.json().get("text", "")
            logger.debug(f"Remote inference successful: {result[:50]}...")
            # Update usage tracking
            current_time = time.time()
            if current_time - self._last_remote_call > self._rate_limit_window:
                self._remote_call_count = 0  # Reset if window has passed
            self._remote_call_count += 1
            self._last_remote_call = current_time
            return result.strip()
        except requests.RequestException as e:
            logger.error(f"Remote inference failed: {str(e)}")
            return None

    def should_use_remote(self, prompt: str) -> bool:
        """Decide whether to use remote inference based on conditions."""
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))

        # Check local model availability
        has_local_model = hasattr(self, "model") and self.model is not None

        # Check prompt complexity (simple heuristic: length)
        prompt_length = len(prompt)
        is_complex = prompt_length > 200  # Arbitrary threshold; adjust as needed

        # Check rate limit status
        current_time = time.time()
        if current_time - self._last_remote_call > self._rate_limit_window:
            self._remote_call_count = 0  # Reset if window has passed
        rate_limit_ok = self._remote_call_count < self._max_calls_per_window

        # Decision logic
        if not has_local_model:
            logger.debug("No local model, preferring remote")
            return rate_limit_ok
        if is_complex:
            logger.debug("Complex prompt, considering remote")
            return rate_limit_ok
        if rate_limit_ok and prompt_length > 50:  # Small prompts stay local unless rate limit allows
            logger.debug("Rate limit allows, using remote for moderate prompt")
            return True
        logger.debug("Defaulting to local inference")
        return False

    def generate(self, prompt: str, use_remote: Optional[bool] = None, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Generate text, smartly choosing between local and remote inference."""
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))

        # Allow explicit override
        if use_remote is not None:
            should_use_remote = use_remote
        else:
            should_use_remote = self.should_use_remote(prompt)

        if should_use_remote:
            result = self.remote_infer(prompt, endpoint, **kwargs)
            if result is not None:
                return result
            logger.warning("Remote inference failed, falling back to local model")

        if hasattr(self, "model") and self.model:
            return self.model.generate(prompt, **kwargs)
        raise RuntimeError("No local model available and remote inference failed")

    def set_remote_endpoint(self, endpoint: str, config: Dict[str, Any]):
        """Add or update a remote endpoint configuration."""
        self.REMOTE_ENDPOINTS[endpoint] = config
