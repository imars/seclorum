# seclorum/models/model_managers/__init__.py
from .ollama import OllamaModelManager
from .llama_cpp import LlamaCppModelManager, Llama, llama_chat_apply_template
#from .guidance import GuidanceModelManager, guidance, GuidanceLlamaCpp
from .google import GoogleModelManager
from .mock import MockModelManager
from .chat_template import CustomChatTemplate


__all__ = [
    "OllamaModelManager",
    "LlamaCppModelManager",
    "Llama",
    "llama_chat_apply_template",
    "GuidanceModelManager",
    "guidance",
    "GuidanceLlamaCpp",
    "GoogleModelManager",
    "MockModelManager",
    "CustomChatTemplate"
]
