# seclorum/agents/remote.py (Merged)
import requests
from typing import Optional, Dict, Any
import os
import logging

class Remote:
    """Mixin to provide optional remote inference capabilities to agents."""
    REMOTE_ENDPOINTS = {
        "google_ai_studio": {
            "url": "https://api.googleaistudio.com/v1/models/gemini:generate",  # From current
            "api_key": None,  # Set via env var or config
            "model": "gemini-1.5-flash",  # From proposed
            "headers": {"Content-Type": "application/json"}  # From current
        }
        # Add more endpoints (e.g., Hugging Face) here
    }

    def remote_infer(self, prompt: str, endpoint: str = "google_ai_studio", **kwargs) -> Optional[str]:
        """Perform inference using a remote endpoint."""
        # Use agent's logger if available, else create one
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
            **kwargs  # Allow additional parameters
        }
        headers = endpoint_config["headers"].copy()
        headers["Authorization"] = f"Bearer {api_key}"

        logger.debug(f"Sending inference request to {endpoint}")
        try:
            response = requests.post(endpoint_config["url"], json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json().get("generated_text", "") or response.json().get("text", "")
            logger.debug(f"Remote inference successful: {result[:50]}...")
            return result.strip()
        except requests.RequestException as e:
            logger.error(f"Remote inference failed: {str(e)}")
            return None

    def generate(self, prompt: str, use_remote: bool = False, endpoint: str = "google_ai_studio", **kwargs) -> str:
        """Generate text, using remote inference if enabled, else local model."""
        logger = getattr(self, 'logger', logging.getLogger(f"Agent_{getattr(self, 'name', 'Remote')}"))

        if use_remote:
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
