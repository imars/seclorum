# seclorum/models/model_managers/chat_template.py
from typing import Optional
import logging
import json

try:
    from llama_cpp import llama_chat_apply_template
except ImportError:
    llama_chat_apply_template = None

logger = logging.getLogger("ModelManager")

class CustomChatTemplate:
    """Custom chat template mimicking Ollama's LLaMA 3.2 template."""
    def __init__(self, model_name: str):
        self.model_name = model_name
        if not llama_chat_apply_template:
            raise ImportError("llama_chat_apply_template not available; cannot initialize CustomChatTemplate")

    def apply_chat_template(self, messages, system: Optional[str] = None, tools: Optional[list] = None):
        if "llama3.2" in self.model_name.lower():
            try:
                prompt = ""
                if system:
                    prompt += f"<|begin_of_text|>System: {system}\n"
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    if role == "user":
                        prompt += f"User: {content}\n"
                    elif role == "assistant":
                        prompt += f"Assistant: {content}\n"
                prompt += "<|eot_id|>"
                return prompt
            except Exception as e:
                logger.error(f"Failed to apply LLaMA 3.2 chat template: {str(e)}")
                raise
        elif "mistral" in self.model_name.lower():
            prompt = ""
            for i, msg in enumerate(messages):
                role = msg["role"]
                content = msg["content"]
                if role in ["system", "user"]:
                    if role == "system" or (role == "user" and i == 0 and system):
                        prompt += f"[INST] {system or ''}\n\n{content} [/INST]"
                    else:
                        prompt += f"[INST] {content} [/INST]"
                elif role == "assistant":
                    prompt += f"{content}</s>"
                elif role == "tool":
                    prompt += f"[TOOL_RESULTS] {{\"content\": {json.dumps(content)}}} [/TOOL_RESULTS]"
            return prompt
        elif "deepseek" in self.model_name.lower():
            prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                if role == "system":
                    prompt += f"System: {content}\n"
                elif role == "user":
                    prompt += f"User: {content}\n"
                elif role == "assistant":
                    prompt += f"Assistant: {content}\n"
            return prompt
        else:
            prompt = ""
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                prompt += f"### {role.capitalize()}\n{content}\n"
            return prompt
