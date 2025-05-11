# tests/test_outlines.py
import argparse
import json
import logging
import outlines
from outlines.models import LlamaCpp
from seclorum.models.managers.outlines import OutlinesModelManager
from seclorum.models.managers.google import GoogleModelManager
from seclorum.agents.remote import Remote
from seclorum.models.plan import Plan
import re

logger = logging.getLogger(__name__)

class TestAgent(Remote):
    """Mock agent to test remote and local inference."""
    def __init__(self, model_manager):
        self.model = model_manager
        self.logger = logger
        self.name = "TestAgent"

def strip_markdown_json(text: str) -> str:
    """Strip Markdown code fences from JSON output."""
    return re.sub(r'```(?:json)?\n([\s\S]*?)\n```', r'\1', text).strip()

def normalize_json_output(text: str, use_remote: bool) -> str:
    """Normalize JSON output to match Plan schema."""
    try:
        data = json.loads(text)
        if use_remote and "plan" in data and "tasks" in data["plan"]:
            # Gemini output: {"plan": {"tasks": [...]}} -> {"subtasks": [...]}
            data = {"subtasks": data["plan"]["tasks"]}
            return json.dumps(data, ensure_ascii=True)
        return text
    except json.JSONDecodeError:
        logger.warning("Failed to normalize JSON output; returning original text")
        return text

def test_outlines(model_name, use_remote=False):
    manager = None
    try:
        if use_remote:
            print(f"INFO:__main__:Initializing GoogleModelManager with {model_name}")
            manager = GoogleModelManager(model_name=model_name)
        else:
            print(f"INFO:__main__:Initializing OutlinesModelManager with {model_name}")
            manager = OutlinesModelManager(model_name=model_name)

        agent = TestAgent(manager)
        print("INFO:__main__:Generating JSON output")

        prompt = (
            "Create a simple plan with 2-3 subtasks for writing a 'Hello, World!' program in Python. "
            "Each subtask should include: task_id (string), description (string), language (string), "
            "parameters (dict with 'output_files' list), and dependencies (list of task_id strings). "
            "Return the plan as valid JSON with a top-level 'subtasks' field conforming to the provided schema, "
            "without Markdown formatting or extra text."
        )
        schema = Plan.model_json_schema()
        system = (
            "You are a helpful assistant. Generate valid JSON output with a top-level 'subtasks' field "
            "according to the provided schema, with no extra text, reasoning, or dialogue."
        )

        # Use Remote mixin's generate method
        result = agent.generate(
            prompt,
            system=system,
            function_call={"schema": schema},
            max_tokens=4096 if not use_remote else 512,
            temperature=0.1 if model_name.startswith("qwen3") else 0.7,
            use_remote=use_remote,
            endpoint="google_ai_studio"
        )

        # Strip Markdown formatting and normalize JSON
        cleaned_result = strip_markdown_json(result)
        normalized_result = normalize_json_output(cleaned_result, use_remote)
        print(f"INFO:__main__:Generated output: {normalized_result[:200]}...")
        logger.debug(f"Raw output: {result}")
        logger.debug(f"Cleaned output: {cleaned_result}")
        logger.debug(f"Normalized output: {normalized_result}")

        # Parse and validate JSON
        result_dict = json.loads(normalized_result)
        assert "subtasks" in result_dict, "Output must contain 'subtasks' field"
        assert isinstance(result_dict["subtasks"], list), "'subtasks' must be a list"
        assert 2 <= len(result_dict["subtasks"]) <= 3, "Plan must have 2-3 subtasks"
        for subtask in result_dict["subtasks"]:
            assert "task_id" in subtask, "Subtask must have 'task_id'"
            assert "description" in subtask, "Subtask must have 'description'"
            assert "language" in subtask, "Subtask must have 'language'"
            assert "parameters" in subtask, "Subtask must have 'parameters'"
            assert "output_files" in subtask["parameters"], "Parameters must have 'output_files'"
            assert "dependencies" in subtask, "Subtask must have 'dependencies'"
        Plan.model_validate_json(normalized_result)
        logger.info(f"JSON output validated successfully for model {model_name}")
    except json.JSONDecodeError as e:
        print(f"ERROR:__main__:JSON parsing failed: {str(e)}")
        print(f"ERROR:__main__:Problematic output: {result[:500]}")
        raise
    except Exception as e:
        print(f"ERROR:__main__:Error: {str(e)}")
        if any(term in str(e).lower() for term in ["qwen3", "phi", "transformers", "token"]):
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
    parser = argparse.ArgumentParser(description="Test Outlines JSON generation with a specified model")
    parser.add_argument("--model", default="qwen3:1.7b", help="Model name (e.g., qwen3:1.7b, gemini-1.5-flash)")
    parser.add_argument("--remote", action="store_true", help="Use remote inference (Google AI Studio)")
    args = parser.parse_args()
    test_outlines(args.model, use_remote=args.remote)
