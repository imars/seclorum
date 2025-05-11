# seclorum/models/managers/outlines/utils.py
import re
import json
from typing import Any

def format_prompt(system: str, prompt: str, architecture: str) -> str:
    """Format prompt based on model architecture."""
    if architecture == "qwen3":
        return (
            f"<|im_start|>system\n{system}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    elif architecture == "phi4":
        return f"<|user|> {system}\n{prompt} <|assistant|> "
    elif architecture == "transformers":
        return f"<|user|> {system}\n{prompt} <|assistant|> "
    else:
        return (
            f"<|start_header_id|>system<|end_header_id>\n\n{system}<|eot_id>\n"
            f"<|start_header_id|>user<|end_header_id>\n\n{prompt}<|eot_id>\n"
            f"<|start_header_id|>assistant<|end_header_id>\n\n"
        )

def clean_dict(d: Any) -> Any:
    """Recursively clean a dictionary to ensure printable ASCII characters."""
    if isinstance(d, dict):
        return {k: clean_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [clean_dict(v) for v in d]
    elif isinstance(d, str):
        return ''.join(c for c in d if ord(c) < 128 and c.isprintable())
    return d

def strip_chat_tokens(text: str) -> str:
    """Strip chat template tokens from text."""
    tokens_to_strip = [
        "<|im_start|>", "<|im_end|>", "<|eot_id>", "<|start_header_id|>", "<|end_header_id>",
        "<|start_headerity|>", "<|end_headerity|>", "<think>", "</think>", "<tool_call>", "</tool_call>",
        "<tool_response>", "</tool_response>", "<|endoftext|>", "<|user|>", "<|assistant|>"
    ]
    for token in tokens_to_strip:
        text = text.replace(token, "")
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()
