# seclorum/models/managers/outlines/settings.py
import os

# Mapping of GGUF model architectures to Hugging Face tokenizer models
TOKENIZER_MAPPING = {
    "qwen3": "Qwen/Qwen1.5-4B",
    "phi4": "microsoft/Phi-3-mini-4k-instruct",
}

# Architectures known to have tokenization issues with llama.cpp
PROBLEMATIC_ARCHITECTURES = {"qwen3", "phi4"}

# Supported model architectures
SUPPORTED_ARCHITECTURES = [
    "llama", "mistral", "deepseek", "gemma", "phi3", "phi4", "qwen2", "qwen3"
]

# Known invalid token IDs for llama.cpp tokenizer
INVALID_TOKENS = {29333}  # e.g., '�'

# Cache settings
OUTLINES_CACHE_DIR = os.environ.get("OUTLINES_CACHE_DIR", "/tmp/outlines_cache")

# Model-specific generation parameters
MODEL_PARAMS = {
    "llama3.2:latest": {"temperature": 0.1, "top_k": 20},
    "deepseek-r1:8b": {"temperature": 0.1, "top_k": 20},
    "qwen3": {"max_tokens": 40960, "temperature": 0.1, "prompt_suffix": " /no_think"},
    "phi4": {"max_tokens": 8192, "temperature": 0.7},
    "transformers": {"max_tokens": 512, "temperature": 0.7},
}

# Default generation parameters
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TOP_K = 40
MAX_RETRIES = 5

# llama_cpp_python minimum version for problematic models
MIN_LLAMA_CPP_VERSION = "0.3.8"
