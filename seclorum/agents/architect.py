# seclorum/agents/architect.py
from typing import Tuple, Any, Optional, Dict, List
from seclorum.agents.agent import Agent
from seclorum.models import Plan, Task
from seclorum.agents.settings import Settings
from seclorum.languages import LANGUAGE_HANDLERS
import logging
import json
import re
import uuid

try:
    import guidance
except ImportError:
    guidance = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Architect(Agent):
    def __init__(self, name: str, session_id: str, model_manager=None):
        super().__init__(name, session_id, model_manager)
        logger.info(f"Architect initialized: name={name}, session_id={session_id}")

    def validate_plan(self, raw_plan: str) -> bool:
        """Validate that the plan includes a configuration subtask and is valid JSON."""
        try:
            plan_data = json.loads(raw_plan)
            if not isinstance(plan_data, dict) or "subtasks" not in plan_data:
                logger.debug("Validation failed: Plan is not a dict or missing 'subtasks'")
                return False
            for subtask in plan_data.get("subtasks", []):
                if "config_output" in subtask.get("parameters", {}).get("output_files", []):
                    return True
            logger.debug("Validation failed: No subtask includes 'config_output'")
            return False
        except json.JSONDecodeError as e:
            logger.debug(f"Validation failed due to JSONDecodeError: {str(e)}")
            return False

    def clean_raw_plan(self, raw_plan: str) -> str:
        """Clean raw plan output to extract valid JSON."""
        cleaned_plan = raw_plan.strip()
        cleaned_plan = re.sub(r'^```json\n|```$|^.*?\n\s*\{|\s*Note:.*$', '', cleaned_plan, flags=re.MULTILINE | re.DOTALL)
        cleaned_plan = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned_plan)
        cleaned_plan = re.sub(r',\s*([}\]])', r'\1', cleaned_plan)
        cleaned_plan = re.sub(r'\[\s*,', '[', cleaned_plan)
        cleaned_plan = re.sub(r'\{\s*,', '{', cleaned_plan)
        cleaned_plan = re.sub(r'//.*$', '', cleaned_plan, flags=re.MULTILINE)
        cleaned_plan = re.sub(r'/\*.*?\*/', '', cleaned_plan, flags=re.DOTALL)
        cleaned_plan = re.sub(r"'([^']*)'", r'"\1"', cleaned_plan)
        cleaned_plan = re.sub(r'\s*(?:Note:.*|This plan.*|\}\s*[^}]*)$', '}', cleaned_plan, flags=re.DOTALL)
        cleaned_plan = re.sub(r'}\s*}+$', '}', cleaned_plan)
        cleaned_plan = re.sub(r':\s*([^\[{"])', r': "\1', cleaned_plan)
        cleaned_plan = re.sub(r'\[\s*([^\]]*)\s*([^\]\s])', r'[\1]', cleaned_plan)
        while cleaned_plan.count('{') > cleaned_plan.count('}'):
            cleaned_plan += '}'
        while cleaned_plan.count('[') > cleaned_plan.count(']'):
            cleaned_plan += ']'

        json_match = re.search(r'\{[\s\S]*\}', cleaned_plan)
        if not json_match:
            logger.error(f"No valid JSON object found in raw plan: {cleaned_plan[:200]}...")
            return "{}"
        cleaned_plan = json_match.group(0)

        try:
            json.loads(cleaned_plan)
            logger.debug(f"Cleaned plan: {cleaned_plan[:200]}...")
        except json.JSONDecodeError as e:
            logger.warning(f"Cleaned plan is still invalid JSON: {str(e)}")
            cleaned_plan = "{}"
        return cleaned_plan

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate a retry prompt with generic guidance."""
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            try:
                plan_data = json.loads(previous_result)
                if not any("config_output" in subtask.get("parameters", {}).get("output_files", [])
                           for subtask in plan_data.get("subtasks", [])):
                    issues.append("Missing 'config_output' in configuration subtask's output_files")
                if not plan_data.get("subtasks"):
                    issues.append("No 'subtasks' array found")
            except json.JSONDecodeError:
                issues.append("Invalid JSON format, possibly due to truncation, missing commas, or non-JSON text")

        if not issues:
            issues.append("Output did not meet requirements")

        feedback = "\n".join([f"- {issue}" for issue in issues])
        guidance = (
            "Output ONLY a valid JSON object with double quotes for strings, "
            "no trailing or leading commas, no comments, no markdown, no code block markers (```), "
            "and no text outside the JSON object. "
            "Each subtask must have 'description', 'language', 'parameters' with 'output_files', "
            "'dependencies', and 'prompt'. The configuration subtask MUST include 'config_output' in 'output_files'. "
            "Generate 5–10 subtasks to cover all necessary components efficiently."
        )

        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Define JSON schema for function-calling and Guidance."""
        return {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "language": {"type": "string", "enum": ["html", "css", "javascript", "json", "text"]},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "output_files": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["output_files"]
                            },
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "prompt": {"type": "string"}
                        },
                        "required": ["description", "language", "parameters", "dependencies", "prompt"]
                    },
                    "minItems": 5,
                    "maxItems": 10  # Allow flexibility up to 10 subtasks
                }
            },
            "required": ["subtasks"]
        }

    def process_task(self, task: Task) -> Tuple[str, Any, str]:
        logger.info(f"Processing task {task.task_id}: description={task.description[:100]}...")
        try:
            prompt = self.get_prompt(task)
            max_tokens = task.parameters.get(
                "max_tokens",
                8192 if task.parameters.get("use_remote", False)
                else 4096
            )
            infer_kwargs = {
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "timeout": Settings.Architect.ProcessTask.TIMEOUT_DEFAULT,
                "raw": True if self.model.provider == "ollama" else False,
                "function_call": {"schema": self.get_schema()}
            }

            logger.info(f"Calling infer with use_remote={task.parameters.get('use_remote', False)}, max_tokens={max_tokens}, raw={infer_kwargs.get('raw')}")
            raw_plan = self.infer(
                prompt=prompt,
                task=task,
                use_remote=task.parameters.get("use_remote", False),
                use_context=True,
                validate_fn=self.validate_plan,
                max_retries=3,  # Reduced retries with Guidance
                **infer_kwargs
            )
            logger.info(f"Raw plan output length: {len(raw_plan)}")

            try:
                plan_data = json.loads(raw_plan)
                logger.info(f"Parsed plan: {json.dumps(plan_data, indent=2)[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON at position {e.pos}: {str(e)}")
                logger.debug(f"Raw plan causing error: {raw_plan[:500]}...")
                raw_plan_cleaned = self.clean_raw_plan(raw_plan)
                logger.debug(f"Cleaned plan error context: {raw_plan_cleaned[max(0, e.pos-50):e.pos+50]}")
                subtasks = self.create_fallback_subtasks(task)
                fallback_plan = {
                    "subtasks": [
                        {
                            "description": s.description,
                            "language": s.parameters.get("language"),
                            "parameters": {"output_files": s.parameters.get("output_files", [])},
                            "dependencies": s.dependencies,
                            "prompt": s.prompt
                        } for s in subtasks
                    ]
                }
                self.store_output(task, "generated", fallback_plan, prompt=prompt)
                return "generated", Plan(subtasks=subtasks), raw_plan_cleaned

            if not isinstance(plan_data, dict) or "subtasks" not in plan_data:
                logger.warning("Plan missing subtasks, using fallback")
                subtasks = self.create_fallback_subtasks(task)
                fallback_plan = {
                    "subtasks": [
                        {
                            "description": s.description,
                            "language": s.parameters.get("language"),
                            "parameters": {"output_files": s.parameters.get("output_files", [])},
                            "dependencies": s.dependencies,
                            "prompt": s.prompt
                        } for s in subtasks
                    ]
                }
                self.store_output(task, "generated", fallback_plan, prompt=prompt)
                return "generated", Plan(subtasks=subtasks), raw_plan

            subtasks = []
            task_id_map = {}
            for subtask_data in plan_data.get("subtasks", []):
                parameters = subtask_data.get("parameters", {})
                output_files = parameters.get("output_files", [])
                if not output_files:
                    logger.warning(f"No output_files in subtask, skipping: {subtask_data}")
                    continue
                language = subtask_data.get("language", task.parameters.get("language", "javascript")).lower()
                if language == "none":
                    language = "text"
                handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
                output_files = handler.map_output_files(output_files, task)
                task_id = str(uuid.uuid4())
                dependency_descs = subtask_data.get("dependencies", [])
                dependency_ids = []
                for desc in dependency_descs:
                    for existing_desc, tid in task_id_map.items():
                        if desc.lower() == existing_desc.lower():
                            dependency_ids.append(tid)
                            break
                subtask = Task(
                    task_id=task_id,
                    description=subtask_data.get("description", ""),
                    parameters={
                        "language": language,
                        "output_files": output_files
                    },
                    dependencies=dependency_ids,
                    prompt=subtask_data.get("prompt", handler.get_code_prompt(task, output_files[0]))
                )
                task_id_map[subtask.description] = task_id
                subtasks.append(subtask)

            html_task_ids = {s.task_id for s in subtasks if s.parameters.get("language").lower() == "html"}
            for i, subtask in enumerate(subtasks):
                if subtask.parameters.get("language").lower() in ["javascript", "css"] and html_task_ids:
                    subtask.dependencies.extend([tid for tid in html_task_ids if tid not in subtask.dependencies])

            js_task_ids = {s.task_id for s in subtasks if s.parameters.get("language").lower() == "javascript"}
            for i, subtask in enumerate(subtasks):
                if subtask.parameters.get("language").lower() == "text" and js_task_ids:
                    subtask.dependencies.extend([tid for tid in js_task_ids if tid not in subtask.dependencies])

            config_included = any("config_output" in s.parameters.get("output_files", []) for s in subtasks)
            if not config_included:
                logger.warning("config_output missing, adding configuration subtask")
                language = task.parameters.get("language", "javascript").lower()
                handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
                task_id = str(uuid.uuid4())
                subtask = Task(
                    task_id=task_id,
                    description="Implement configuration",
                    parameters={
                        "language": language,
                        "output_files": handler.map_output_files(["config_output"], task)
                    },
                    dependencies=list(html_task_ids),
                    prompt=handler.get_code_prompt(task, "config_output")
                )
                task_id_map[subtask.description] = task_id
                subtasks.append(subtask)

            if not subtasks:
                logger.warning("No valid subtasks, using fallback")
                subtasks = self.create_fallback_subtasks(task)
                fallback_plan = {
                    "subtasks": [
                        {
                            "description": s.description,
                            "language": s.parameters.get("language"),
                            "parameters": {"output_files": s.parameters.get("output_files", [])},
                            "dependencies": s.dependencies,
                            "prompt": s.prompt
                        } for s in subtasks
                    ]
                }
                self.store_output(task, "generated", fallback_plan, prompt=prompt)
                return "generated", Plan(subtasks=subtasks), raw_plan

            self.store_output(task, "generated", plan_data, prompt=prompt)
            return "generated", Plan(subtasks=subtasks), raw_plan
        except Exception as e:
            logger.error(f"Error generating plan for task {task.task_id}: {str(e)}")
            subtasks = self.create_fallback_subtasks(task)
            fallback_plan = {
                "subtasks": [
                    {
                        "description": s.description,
                        "language": s.parameters.get("language"),
                        "parameters": {"output_files": s.parameters.get("output_files", [])},
                        "dependencies": s.dependencies,
                        "prompt": s.prompt
                    } for s in subtasks
                ]
            }
            self.store_output(task, "failed", fallback_plan, prompt=prompt)
            return "failed", Plan(subtasks=subtasks), raw_plan

    def create_fallback_subtasks(self, task: Task) -> List[Task]:
        """Create fallback subtasks using LanguageHandler for output files and prompts."""
        logger.info("Generating fallback subtasks")
        output_files = task.parameters.get("output_files", ["main_output"])
        subtasks = []
        task_id_map = {}

        for output_file in output_files:
            language = (
                "javascript" if output_file.endswith(".js") else
                "html" if output_file.endswith(".html") else
                "css" if output_file.endswith(".css") else
                "json" if output_file.endswith(".json") else
                task.parameters.get("language", "javascript")
            )
            handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
            specific_files = handler.map_output_files([output_file], task)
            task_id = str(uuid.uuid4())
            subtask = Task(
                task_id=task_id,
                description=f"Generate {language} component for {output_file}",
                parameters={
                    "language": language,
                    "output_files": specific_files
                },
                dependencies=[],
                prompt=handler.get_code_prompt(task, output_file)
            )
            task_id_map[subtask.description] = task_id
            subtasks.append(subtask)

        language = task.parameters.get("language", "javascript").lower()
        handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
        task_id = str(uuid.uuid4())
        core_subtask = Task(
            task_id=task_id,
            description="Implement core functionality and configuration",
            parameters={
                "language": language,
                "output_files": handler.map_output_files(["main_output", "config_output"], task)
            },
            dependencies=[s.task_id for s in subtasks if s.parameters.get("language") == "html"],
            prompt=handler.get_code_prompt(task, "main_output")
        )
        task_id_map[core_subtask.description] = task_id
        subtasks.append(core_subtask)

        additional_subtasks = [
            (
                "Write unit tests",
                language,
                ["test_output"],
                [core_subtask.task_id],
                handler.get_code_prompt(task, "test_output")
            ),
            (
                "Reference external resources",
                "text",
                ["resources.txt"],
                [core_subtask.task_id],
                "List external resources required for the application."
            )
        ]
        for description, lang, files, deps, prompt in additional_subtasks:
            task_id = str(uuid.uuid4())
            handler = LANGUAGE_HANDLERS.get(lang, LANGUAGE_HANDLERS["javascript"])
            subtask = Task(
                task_id=task_id,
                description=description,
                parameters={
                    "language": lang,
                    "output_files": handler.map_output_files(files, task)
                },
                dependencies=deps,
                prompt=prompt
            )
            task_id_map[description] = task_id
            subtasks.append(subtask)

        html_task_ids = {s.task_id for s in subtasks if s.parameters.get("language").lower() == "html"}
        for subtask in subtasks:
            if subtask.parameters.get("language").lower() in ["javascript", "css"] and html_task_ids:
                subtask.dependencies.extend([tid for tid in html_task_ids if tid not in subtask.dependencies])

        js_task_ids = {s.task_id for s in subtasks if s.parameters.get("language").lower() == "javascript"}
        for subtask in subtasks:
            if subtask.parameters.get("language").lower() == "text" and js_task_ids:
                subtask.dependencies.extend([tid for tid in js_task_ids if tid not in subtask.dependencies])

        return subtasks

    def get_prompt(self, task: Task) -> str:
        """Create a language-agnostic prompt for generating a plan with subtasks."""
        output_files = task.parameters.get("output_files", ["main_output"])
        max_tokens = task.parameters.get(
            "max_tokens",
            8192 if task.parameters.get("use_remote", False)
            else 4096
        )
        system_prompt = (
            "You are a coding assistant that generates a JSON object with a 'subtasks' array for a web-based application. "
            "Output ONLY valid JSON with double quotes for strings, no comments, no markdown, no code block markers (```), and no text outside the JSON object. "
            "Each subtask must have 'description', 'language', 'parameters' with 'output_files', 'dependencies', and 'prompt'. "
            "The configuration subtask MUST include 'config_output' in 'output_files'. "
            "Generate 5–10 subtasks to cover all necessary components efficiently."
        )
        user_prompt = (
            f"Task Description: {task.description}\n"
            f"Required output files: {', '.join(output_files)}.\n"
            f"Requirements:\n"
            f"- Generate 5–10 subtasks covering HTML, CSS, JavaScript, JSON, and text pipelines.\n"
            f"- Include {', '.join(output_files)} in relevant subtasks.\n"
            f"- The core functionality subtask must include 'main_output' and 'config_output' in 'output_files'.\n"
            f"- Each subtask must include:\n"
            f"  - 'description': A unique, brief description.\n"
            f"  - 'language': One of html, css, javascript, json, or text.\n"
            f"  - 'parameters': An object with 'output_files' listing file names.\n"
            f"  - 'dependencies': A list of subtask descriptions (not IDs) this subtask depends on.\n"
            f"  - 'prompt': Instructions for implementing the subtask, using the language's conventions.\n"
            f"- CSS subtasks depend on HTML subtasks.\n"
            f"- JavaScript subtasks depend on HTML subtasks.\n"
            f"- Text subtasks depend on JavaScript subtasks.\n"
            f"Example:\n"
            f'{{"subtasks": ['
            f'{{"description": "Create UI structure", "language": "html", "parameters": {{"output_files": ["main_output"]}}, "dependencies": [], "prompt": "Generate HTML structure for the application."}},'
            f'{{"description": "Apply styling", "language": "css", "parameters": {{"output_files": ["main_output"]}}, "dependencies": ["Create UI structure"], "prompt": "Create CSS for UI components and layout."}},'
            f'{{"description": "Implement core functionality", "language": "javascript", "parameters": {{"output_files": ["main_output", "config_output"]}}, "dependencies": ["Create UI structure"], "prompt": "Implement core functionality and configuration."}},'
            f'{{"description": "Configure project", "language": "json", "parameters": {{"output_files": ["main_output"]}}, "dependencies": [], "prompt": "Define project configuration."}},'
            f'{{"description": "List resources", "language": "text", "parameters": {{"output_files": ["main_output"]}}, "dependencies": ["Implement core functionality"], "prompt": "List external resources."}}'
            f']}}'
        )

        if self.model.provider == "guidance" and guidance:
            return (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"Generate a JSON object conforming to the following schema:\n{json.dumps(self.get_schema(), indent=2)}\n"
                f"{system_prompt}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
        elif self.model.provider == "ollama":
            return f"{system_prompt}\n\n{user_prompt}"
        elif self.model.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        elif self.model.provider == "llama_cpp":
            return (
                f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
                f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
        return f"{system_prompt}\n\n{user_prompt}"
