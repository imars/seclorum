# seclorum/agents/settings.py
"""Centralized settings for agent configurations."""

import os
from typing import Dict, Any


class Settings:
    class Agent:
        class RemoteInfer:
            MAX_TOKENS_DEFAULT = 8192
            TIMEOUT_DEFAULT = 30
            TEMPERATURE_DEFAULT = 0.7
            RATE_LIMIT_WINDOW = 60  # Seconds
            MAX_CALLS_PER_WINDOW = 10  # Default max calls per window
            # Remote endpoint configurations
            REMOTE_ENDPOINTS: Dict[str, Dict[str, Any]] = {
                "google_ai_studio": {
                    "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
                    "api_key_env": "GOOGLE_AI_STUDIO_API_KEY",  # Environment variable for API key
                    "model": "gemini-1.5-flash",
                    "headers": {"Content-Type": "application/json"},
                    "rate_limit_window": 60,  # Endpoint-specific rate limit window
                    "max_calls_per_window": 10,  # Endpoint-specific max calls
                },
                # Example for future endpoints
                # "openai": {
                #     "url": "https://api.openai.com/v1/chat/completions",
                #     "api_key_env": "OPENAI_API_KEY",
                #     "model": "gpt-4",
                #     "headers": {"Content-Type": "application/json", "Authorization": "Bearer {api_key}"},
                #     "rate_limit_window": 60,
                #     "max_calls_per_window": 100,
                # }
            }

        class Infer:
            MAX_RETRIES = 3
            MAX_TOKENS_DEFAULT = 16384
            TIMEOUT_DEFAULT = 300
            TEMPERATURE_DEFAULT = 0.7

    class Architect:
        class ProcessTask:
            MAX_TOKENS_DEFAULT = 16384
            MAX_TOKENS_DEFAULT_REMOTE = 8192
            TIMEOUT_DEFAULT = 300

    class Guidance:
        TEMPERATURE_DEFAULT = 0.0  # Low temperature for deterministic JSON output
        MAX_TOKENS_DEFAULT = 16384  # Match Architect max_tokens

    @classmethod
    def get_endpoint_config(cls, endpoint: str) -> Dict[str, Any]:
        """Retrieve configuration for a specific remote endpoint."""
        return cls.Agent.RemoteInfer.REMOTE_ENDPOINTS.get(endpoint, {})
