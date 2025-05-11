# tests/test_outlines_minimal.py
import argparse
import outlines
from outlines.models import LlamaCpp
from seclorum.models.managers.outlines import OutlinesModelManager
import logging

logger = logging.getLogger(__name__)

def test_outlines_minimal(model_name):
    manager = None
    try:
        print(f"INFO:__main__:Initializing OutlinesModelManager with {model_name}")
        manager = OutlinesModelManager(model_name=model_name)
        model = LlamaCpp(model=manager.llama) if not model_name.startswith("transformers:") else manager.model
        generator = outlines.generate.text(model)
        prompt = "Output the exact phrase 'Hello, world!' followed by a brief greeting (e.g., 'Welcome!'), with no explanations, code, or extra content."
        max_tokens = 50 if not model_name.startswith("transformers:") else 30
        result = generator(prompt, max_tokens=max_tokens, temperature=0.7)
        print(f"INFO:__main__:Generated output: {result}")
        logger.debug(f"Raw output: {result}")
        if "Hello, world!" not in result:
            logger.warning(f"Output does not contain 'Hello, world!' for model {model_name}")
        if any(word in result.lower() for word in ["code", "script", "program", "python", "javascript"]):
            logger.warning(f"Output contains programming-related terms for model {model_name}")
        assert not any(
            token in result for token in ["<|im_start|>", "<|im_end|>", "<|eot_id>", "<think>", "<tool_call>"]
        ), "Output must not contain chat template tokens"
    except Exception as e:
        print(f"ERROR:__main__:Error: {str(e)}")
        if any(term in str(e).lower() for term in ["qwen3", "phi", "transformers"]):
            print(
                "ERROR:__main__:Model may require reinstalling dependencies (e.g., llama_cpp_python, transformers). "
                "See https://github.com/abetlen/llama-cpp-python#installation-from-source or pip install transformers"
            )
        raise
    finally:
        if manager is not None:
            try:
                manager.close()
            except Exception as e:
                print(f"ERROR:__main__:Error closing manager: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test minimal Outlines text generation with a specified model")
    parser.add_argument("--model", default="qwen3:1.7b", help="Model name (e.g., qwen3:1.7b, qwen3:4b, phi4-mini-reasoning, mistral:latest, llama3.2:latest, deepseek-r1:8b, transformers:facebook/opt-125m)")
    args = parser.parse_args()
    test_outlines_minimal(args.model)
