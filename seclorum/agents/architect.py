from typing import Any, Dict, List, Optional, Tuple, Callable
from seclorum.models import Task, Plan
from seclorum.agents.agent import Agent
from seclorum.utils.logger import logger
from seclorum.languages import LANGUAGE_HANDLERS
from seclorum.agents.settings import Settings
import json
import uuid
import sqlite3

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager=None, model_name: str = "gemini-1.5-flash", memory_kwargs: Optional[Dict] = None):
        memory_kwargs = memory_kwargs or {}
        super().__init__(name=f"Architect_{task_id}", session_id=session_id, model_manager=model_manager, model_name=model_name, memory_kwargs=memory_kwargs)
        logger.info(f"Architect initialized: name=Architect_{task_id}, session_id={session_id}")

    def get_prompt(self, task: Task) -> str:
        language = task.parameters.get("language", "javascript").lower()
        handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
        output_files = handler.map_output_files(["main_output", "config_output", "test_output"], task)
        prompt = (
            f"Task Description:\n{task.description}\n\n"
            f"Generate a JSON plan for implementing the described application. "
            f"The plan should include 5–10 subtasks to cover HTML, JavaScript, CSS, package.json, and README.md. "
            f"Each subtask must have:\n"
            f"- 'description': A brief description of the subtask.\n"
            f"- 'language': The programming language (e.g., 'html', 'javascript', 'css', 'json', 'text').\n"
            f"- 'parameters': An object with 'output_files' listing the files to generate (e.g., {output_files}).\n"
            f"- 'dependencies': A list of subtask descriptions that this subtask depends on.\n"
            f"- 'prompt': A specific prompt for the Generator agent to produce the code or content.\n"
            f"Return a JSON object with a 'subtasks' array, using double quotes for strings, "
            f"no trailing commas, no comments, no markdown, and no text outside the JSON object."
        )
        self.log_update(f"Generated prompt for task {task.task_id}: {prompt[:200]}...")
        return prompt

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            try:
                cleaned_result = self.strip_markdown_json(previous_result)
                plan_data = json.loads(cleaned_result)
                if not plan_data.get("subtasks"):
                    issues.append("No 'subtasks' array found")
            except json.JSONDecodeError:
                issues.append("Invalid JSON format")
        if not issues:
            issues.append("Output did not meet requirements")
        feedback = "\n".join([f"- {issue}" for issue in issues])
        guidance = (
            "Output ONLY a valid JSON object with double quotes for strings, "
            "no trailing or leading commas, no comments, no markdown, no code block markers (```), "
            "and no text outside the JSON object. "
            "Each subtask must have 'description', 'language', 'parameters' with 'output_files', "
            "'dependencies', and 'prompt'. "
            "Generate 5–10 subtasks to cover HTML, JavaScript, CSS, package.json, and README.md efficiently."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "language": {"type": "string"},
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "output_files": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    }
                                },
                                "required": ["output_files"]
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "prompt": {"type": "string"}
                        },
                        "required": ["description", "language", "parameters", "dependencies", "prompt"]
                    }
                }
            },
            "required": ["subtasks"]
        }

    def strip_markdown_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json") and text.endswith("```"):
            return text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            return text[3:-3].strip()
        return text

    def validate_plan(self, raw_plan: str) -> bool:
        try:
            cleaned_plan = self.strip_markdown_json(raw_plan)
            plan_data = json.loads(cleaned_plan)
            if not isinstance(plan_data, dict) or "subtasks" not in plan_data:
                logger.debug("Validation failed: Plan is not a dict or missing 'subtasks'")
                return False
            return True
        except json.JSONDecodeError as e:
            logger.debug(f"Validation failed due to JSONDecodeError: {str(e)}")
            return False

    def create_fallback_subtasks(self, task: Task) -> List[Task]:
        language = task.parameters.get("language", "javascript").lower()
        handler = LANGUAGE_HANDLERS.get(language, LANGUAGE_HANDLERS["javascript"])
        output_files = handler.map_output_files(["main_output"], task)
        return [
            Task(
                task_id=str(uuid.uuid4()),
                description="Implement main functionality",
                parameters={
                    "language": language,
                    "output_files": output_files
                },
                dependencies=[],
                prompt=handler.get_code_prompt(task, output_files[0])
            )
        ]

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.info(f"Processing task {task.task_id}: description={task.description[:100]}...")
        try:
            prompt = self.get_prompt(task)
            max_tokens = task.parameters.get(
                "max_tokens",
                8192 if task.parameters.get("use_remote", False) else 4096
            )
            infer_kwargs = {
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "timeout": Settings.Architect.ProcessTask.TIMEOUT_DEFAULT,
                "function_call": {"schema": self.get_schema()}
            }
            logger.info(f"Calling infer with use_remote={task.parameters.get('use_remote', False)}, max_tokens={max_tokens}")
            raw_plan = None
            for attempt in range(3):
                try:
                    raw_plan = self.infer(
                        prompt=prompt,
                        task=task,
                        use_remote=task.parameters.get("use_remote", False),
                        use_context=True,
                        validate_fn=self.validate_plan,
                        max_retries=3,
                        **infer_kwargs
                    )
                    logger.info(f"Raw plan output length: {len(raw_plan)}")
                    break
                except (json.JSONDecodeError, sqlite3.ProgrammingError, LockTimeoutError) as e:
                    logger.error(f"Inference attempt {attempt + 1} failed for task {task.task_id}: {str(e)}")
                    continue
            if not raw_plan or not raw_plan.strip():
                logger.error("Empty or invalid raw plan received")
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
                return "generated", Plan(subtasks=subtasks)
            cleaned_plan = self.strip_markdown_json(raw_plan)
            try:
                plan_data = json.loads(cleaned_plan)
                logger.info(f"Parsed plan: {json.dumps(plan_data, indent=2)[:200]}...")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {str(e)}, raw_plan: {raw_plan[:200]}...")
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
                return "generated", Plan(subtasks=subtasks)
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
                return "generated", Plan(subtasks=subtasks)
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
                return "generated", Plan(subtasks=subtasks)
            self.store_output(task, "generated", plan_data, prompt=prompt)
            return "generated", Plan(subtasks=subtasks)
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
            return "failed", Plan(subtasks=subtasks)
