# seclorum/models/managers/outlines/tokenizer.py
import logging
from typing import Optional, List
from transformers import AutoTokenizer
import llama_cpp
from .settings import TOKENIZER_MAPPING, INVALID_TOKENS, PROBLEMATIC_ARCHITECTURES

logger = logging.getLogger("ModelManager")

class TokenizerManager:
    def __init__(self, architecture: str, model_name: str, use_custom_tokenizer: bool, llama_instance: Optional[llama_cpp.Llama] = None):
        self.architecture = architecture
        self.model_name = model_name
        self.use_custom_tokenizer = use_custom_tokenizer
        self.llama = llama_instance
        self.custom_tokenizer = None

        # Load custom tokenizer for problematic architectures or models
        if self.use_custom_tokenizer and (self.architecture in PROBLEMATIC_ARCHITECTURES or "qwen3" in model_name.lower()):
            tokenizer_model = TOKENIZER_MAPPING.get(self.architecture, TOKENIZER_MAPPING.get("qwen3"))
            if tokenizer_model:
                try:
                    self.custom_tokenizer = AutoTokenizer.from_pretrained(tokenizer_model)
                    logger.info(f"Loaded custom tokenizer {tokenizer_model} for {self.architecture} (model: {model_name})")
                except Exception as e:
                    logger.warning(f"Failed to load custom tokenizer {tokenizer_model}: {str(e)}. Falling back to llama.cpp tokenizer.")
                    self.custom_tokenizer = None
            else:
                logger.warning(f"No custom tokenizer defined for {self.architecture} or {model_name}. Falling back to llama.cpp tokenizer.")
                self.custom_tokenizer = None

    def tokenize(self, text: str, force_custom_tokenizer: bool = False) -> List[int]:
        """Tokenize text using custom or llama.cpp tokenizer."""
        if force_custom_tokenizer or (self.use_custom_tokenizer and self.custom_tokenizer and (self.architecture in PROBLEMATIC_ARCHITECTURES or "qwen3" in self.model_name.lower())):
            logger.info(f"Using custom tokenizer for {self.architecture} (model: {self.model_name})")
            tokens = self.custom_tokenizer.encode(text, add_special_tokens=False)
            # Filter invalid tokens (inspired by PR #892)
            filtered_tokens = [t for t in tokens if t not in INVALID_TOKENS and self._is_valid_token(t)]
            if len(filtered_tokens) < len(tokens):
                logger.warning(f"Filtered {len(tokens) - len(filtered_tokens)} invalid tokens from output")
            return filtered_tokens
        else:
            if not self.llama:
                raise ValueError("llama.cpp instance not initialized for tokenization")
            logger.info(f"Using llama.cpp tokenizer for {self.architecture} (model: {self.model_name})")
            tokens = self.llama.tokenize(text.encode('utf-8', errors='replace'))
            filtered_tokens = [t for t in tokens if t not in INVALID_TOKENS and self._is_valid_token(t)]
            if len(filtered_tokens) < len(tokens):
                logger.warning(f"Filtered {len(tokens) - len(filtered_tokens)} invalid tokens from output")
            return filtered_tokens

    def _is_valid_token(self, token_id: int) -> bool:
        """Check if a token ID is valid (inspired by PR #892)."""
        try:
            if self.custom_tokenizer:
                self.custom_tokenizer.decode([token_id], skip_special_tokens=True)
            elif self.llama:
                self.llama.detokenize([token_id]).decode('utf-8', errors='ignore')
            return True
        except Exception:
            return False

    def detokenize(self, tokens: List[int], force_custom_tokenizer: bool = False) -> str:
        """Detokenize tokens to text using custom or llama.cpp tokenizer."""
        if force_custom_tokenizer or (self.use_custom_tokenizer and self.custom_tokenizer and (self.architecture in PROBLEMATIC_ARCHITECTURES or "qwen3" in self.model_name.lower())):
            logger.info(f"Using custom tokenizer for detokenization for {self.architecture} (model: {self.model_name})")
            text = self.custom_tokenizer.decode(tokens, skip_special_tokens=True)
        else:
            if not self.llama:
                raise ValueError("llama.cpp instance not initialized for detokenization")
            logger.info(f"Using llama.cpp tokenizer for detokenization for {self.architecture} (model: {self.model_name})")
            text = self.llama.detokenize(tokens).decode('utf-8', errors='replace')
        return ''.join(c for c in text if ord(c) < 128)

    def close(self):
        """Clean up custom tokenizer resources."""
        if self.custom_tokenizer:
            try:
                del self.custom_tokenizer
                logger.debug("Closed custom tokenizer")
                self.custom_tokenizer = None
            except Exception as e:
                logger.warning(f"Error closing custom tokenizer: {str(e)}")
