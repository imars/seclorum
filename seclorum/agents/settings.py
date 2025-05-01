# seclorum/agents/settings.py
"""Centralized settings for agent configurations."""

class Settings:
    class Agent:
        class RemoteInfer:
            MAX_TOKENS_DEFAULT = 8192
            TIMEOUT_DEFAULT = 30
            TEMPERATURE_DEFAULT = 0.7

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
