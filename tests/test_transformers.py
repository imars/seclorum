# tests/test_transformers.py
import argparse
import json
import logging
from seclorum.models.plan import Plan
from seclorum.models.managers.transformers import TransformersModelManager

logger = logging.getLogger(__name__)

def test_transformers(model_name):
    manager = None
    try:
        print(f"INFO:__main__:Initializing TransformersModelManager with {model_name}")
        manager = TransformersModelManager(model_name=model_name)

        # Test text generation
        system_prompt = "You are a helpful assistant. Output only the exact response requested, with no explanations, code, programming instructions, or extra content."
        user_prompt = "Output the exact phrase 'Hello, world!' followed by a brief greeting (e.g., 'Welcome!'), with no explanations, code, or extra content."
        print("INFO:__main__:Generating text output")
        result = manager.generate(
            user_prompt,
            system=system_prompt,
            max_tokens=50,
            temperature=0.7,
            top_k=40
        )
        print(f"INFO:__main__:Generated text output: {result}")
        logger.debug(f"Raw text output: {result}")
        if "Hello, world!" not in result:
            logger.warning(f"Text output does not contain 'Hello, world!' for model {model_name}")
        if any(word in result.lower() for word in ["code", "script", "program", "python", "javascript"]):
            logger.warning(f"Text output contains programming-related terms for model {model_name}")

        # Test JSON generation
        system_prompt_json = "You are a helpful assistant. Generate valid JSON output according to the provided schema, with no extra text, reasoning, or dialogue."
        user_prompt_json = (
            "Generate a simple plan with 2-3 subtasks for creating a 'Hello, World!' program in Python. "
            "Each subtask should have 'task_id', 'description', 'language', 'parameters' with 'output_files', "
            "'dependencies', and 'prompt'. Optionally include 'config_output' in one subtask's 'output_files' "
            "if relevant (e.g., for a configuration file)."
        )
        print("INFO:__main__:Generating JSON output")
        result_json = manager.generate(
            user_prompt_json,
            system=system_prompt_json,
            max_tokens=4096,
            temperature=0.7,
            top_k=40,
            function_call={"schema": Plan}
        )
        result_dict = json.loads(result_json)
        print(f"INFO:__main__:Generated JSON output: {json.dumps(result_dict, indent=2)}")
        logger.debug(f"Raw JSON output: {result_json}")
        assert "subtasks" in result_dict, "JSON output must contain 'subtasks'"
        assert 2 <= len(result_dict["subtasks"]) <= 3, "Subtasks must be 2-3"
        if not any("config_output" in task["parameters"].get("output_files", []) for task in result_dict["subtasks"]):
            logger.warning("JSON output does not include 'config_output' in any subtask's 'output_files'")

    except Exception as e:
        print(f"ERROR:__main__:Error: {str(e)}")
        raise
    finally:
        if manager is not None:
            try:
                manager.close()
            except Exception as e:
                print(f"ERROR:__main__:Error closing manager: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Transformers model with Outlines for text and JSON generation")
    parser.add_argument("--model", default="distilgpt2", help="Hugging Face model name (e.g., distilgpt2, meta-llama/Llama-2-7b-chat-hf)")
    args = parser.parse_args()
    test_transformers(args.model)
