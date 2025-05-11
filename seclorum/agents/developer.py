# File: seclorum/agents/developer.py
from typing import Tuple, Any, List, Dict, Optional
from seclorum.agents.aggregate import Aggregate
from seclorum.models import Task, create_model_manager, CodeOutput, CodeResult, Plan
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect
from seclorum.agents.debugger import Debugger
from seclorum.models.task import TaskFactory
import logging
import re
import json
import os
import sys
import timeout_decorator
import hashlib

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Developer(Aggregate):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id, model_manager)
        self.name = "Developer"
        self.model_manager = model_manager or create_model_manager(provider="google_ai_studio", model_name="gemini-1.5-flash")
        self.pipelines: Dict[str, List[dict]] = {}
        self.agent_flow = []
        self.pipeline_cache = {}  # Cache for pipeline configurations
        logger.debug(f"Developer initialized: session_id={session_id}")
        logger.debug(f"Agent classes: Architect={Architect.__name__}, Generator={Generator.__name__}, "
                     f"Tester={Tester.__name__}, Executor={Executor.__name__}, Debugger={Debugger.__name__}")

    def get_prompt(self, task: Task) -> str:
        """Generate prompt for pipeline inference."""
        output_files = task.parameters.get("output_files", ["main_output"])
        system_prompt = (
            "You are a coding assistant that generates a JSON list of development pipelines for a web-based application. "
            "Output ONLY valid JSON with double quotes for strings, no comments, no markdown, no code block markers (```), "
            "and no text outside the JSON object. "
            "Each pipeline must have 'language' (e.g., 'javascript', 'html') and 'output_files' (list of source files)."
        )
        user_prompt = (
            f"Task Description: {task.description}\n"
            f"Required output files: {', '.join(output_files)}.\n"
            f"Requirements:\n"
            f"- Generate pipelines for each language needed to cover {', '.join(output_files)}.\n"
            f"- Each pipeline must include:\n"
            f"  - 'language': One of html, css, javascript, json, or text.\n"
            f"  - 'output_files': List of file names for that language.\n"
            f"Example:\n"
            f'[{{"language": "javascript", "output_files": ["main.js"]}}, '
            f'{{"language": "html", "output_files": ["main.html"]}}]'
        )
        if self.model_manager.provider == "google_ai_studio":
            return f"{system_prompt}\n\n{user_prompt}"
        return f"<|start_header_id|>system<|end_header_id>\n{system_prompt}\n<|start_header_id|>user<|end_header_id>\n{user_prompt}"

    def get_retry_prompt(self, original_prompt: str, previous_result: str, error: Optional[Exception], validation_passed: bool) -> str:
        """Generate retry prompt for failed pipeline inference."""
        issues = []
        if error:
            issues.append(f"Error: {str(error)}")
        if not validation_passed:
            issues.append("Invalid pipeline format: must be a list of objects with 'language' and 'output_files'")
        feedback = "\n".join([f"- {issue}" for issue in issues]) or "Output did not meet requirements"
        guidance = (
            "Output ONLY a valid JSON list of pipeline objects with double quotes for strings, "
            "no trailing or leading commas, no comments, no markdown, no code block markers (```), "
            "and no text outside the JSON list. "
            "Each pipeline must have 'language' and 'output_files'."
        )
        return (
            f"Previous attempt failed. Output:\n\n{previous_result}\n\n"
            f"Issues:\n{feedback}\n\n"
            f"Instructions:\n- {guidance}\n"
            f"Original prompt:\n{original_prompt}"
        )

    def get_schema(self) -> Dict[str, Any]:
        """Return schema for pipeline inference."""
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "output_files": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["language", "output_files"]
            }
        }

    def setup_pipeline(self, task_id: str, language: str, output_files: List[str]) -> List[dict]:
        logger.debug(f"Setting up pipeline for task={task_id}, language={language}, output_files={output_files}")
        generator = Generator(f"{task_id}_{language}_gen", self.session_id, self.model_manager)
        tester = Tester(f"{task_id}_{language}_test", self.session_id, self.model_manager)
        executor = Executor(f"{task_id}_{language}_exec", self.session_id, self.model_manager)
        debugger = Debugger(f"{task_id}_{language}_debug", self.session_id, self.model_manager)

        logger.debug(f"Instantiated agents: Generator={generator.name}, Tester={tester.name}, "
                     f"Executor={executor.name}, Debugger={debugger.name}")

        pipeline = [
            {"agent": generator, "name": generator.name, "deps": [(f"Architect_{task_id}", {"status": "planned"})],
             "output_files": output_files, "language": language},
            {"agent": tester, "name": tester.name, "deps": [(generator.name, {"status": "generated"})],
             "output_files": output_files, "language": language},
            {"agent": executor, "name": executor.name, "deps": [(tester.name, {"status": "tested"})],
             "output_files": output_files, "language": language},
            {"agent": debugger, "name": debugger.name, "deps": [(executor.name, {"status": "tested", "passed": False})],
             "output_files": output_files, "language": language},
        ]

        for step in pipeline:
            self.add_agent(step["agent"], step["deps"])
            logger.debug(f"Added agent {step['name']} to pipeline")
        return pipeline

    def strip_markdown_json(self, text: str) -> str:
        """Strip Markdown code fences from JSON output."""
        return re.sub(r'```(?:json)?\n([\s\S]*?)\n```', r'\1', text).strip()

    @timeout_decorator.timeout(0, timeout_exception=TimeoutError)
    def infer_pipelines(self, task: Task, plan: Any) -> List[Dict[str, Any]]:
        logger.debug(f"Inferring pipelines for task={task.task_id}")
        # Check cache
        plan_hash = hashlib.sha256(f"{str(plan)}:{task.task_id}".encode()).hexdigest()
        if plan_hash in self.pipeline_cache:
            logger.debug(f"Returning cached pipelines for plan_hash={plan_hash}")
            return self.pipeline_cache[plan_hash]

        prompt = (
            f"Given the following development plan:\n{plan}\n\n"
            "Analyze the plan and determine the necessary development pipelines. Each pipeline should handle a specific language and list of output files. "
            "Return a JSON list of objects, each with 'language' (e.g., 'javascript', 'html') and 'output_files' (list of source files, e.g., ['main.js']). "
            "Ensure output_files exclude test files (e.g., no .test.js). Example:\n"
            '[{"language": "javascript", "output_files": ["main.js"]}, {"language": "html", "output_files": ["main.html"]}]'
        )
        try:
            response = self.infer(
                prompt=prompt,
                task=task,
                use_remote=task.parameters.get("use_remote", True),
                function_call={"schema": self.get_schema()}
            )
            logger.debug(f"infer_pipelines response: {response[:200]}...")
            cleaned_response = self.strip_markdown_json(response)
            try:
                data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {str(e)}, trying to fix")
                cleaned_response = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned_response)
                cleaned_response = re.sub(r',\s*]', ']', cleaned_response)
                cleaned_response = re.sub(r',\s*}', '}', cleaned_response)
                data = json.loads(cleaned_response)
            # Normalize Gemini output
            if isinstance(data, dict) and "plan" in data and "tasks" in data["plan"]:
                data = data["plan"]["tasks"]
            elif isinstance(data, dict) and "pipelines" in data:
                data = data["pipelines"]
            pipelines = data if isinstance(data, list) else []
            if not pipelines:
                raise ValueError("No valid pipelines found")
            for p in pipelines:
                if not all(k in p for k in ["language", "output_files"]):
                    raise ValueError("Each pipeline must have 'language' and 'output_files'")
                p["language"] = p["language"].lower()
                p["output_files"] = [re.sub(r'\.(test|spec)\b', '', f) for f in p["output_files"]]
                if p["language"] == "javascript":
                    p["output_files"] = [f if f.endswith(".js") else f + ".js" for f in p["output_files"]]
                elif p["language"] == "html":
                    p["output_files"] = [f if f.endswith(".html") else f + ".html" for f in p["output_files"]]
                elif p["language"] == "css":
                    p["output_files"] = [f if f.endswith(".css") else f + ".css" for f in p["output_files"]]
                elif p["language"] == "json":
                    p["output_files"] = [f if f.endswith(".json") else f + ".json" for f in p["output_files"]]
            logger.debug(f"Inferred pipelines: {pipelines}")
            # Cache the result
            self.pipeline_cache[plan_hash] = pipelines
            return pipelines
        except (json.JSONDecodeError, ValueError, TimeoutError) as e:
            logger.error(f"Pipeline inference failed: {str(e)}, defaulting to task parameters")
            output_files = task.parameters.get("output_files", ["main.js", "main.html", "styles.css", "package.json"])
            pipelines = []
            for file in output_files:
                language = (
                    "javascript" if file.endswith(".js") else
                    "html" if file.endswith(".html") else
                    "css" if file.endswith(".css") else
                    "json" if file.endswith(".json") else
                    "text"
                )
                pipelines.append({"language": language, "output_files": [file]})
            self.pipeline_cache[plan_hash] = pipelines
            return pipelines

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"Developer processing Task {task.task_id}, language={task.parameters.get('language', '')}, "
                     f"parameters={task.parameters}")
        try:
            result = self.orchestrate(task)
            if result is None:
                logger.error("Orchestration returned None, falling back")
                return "failed", CodeOutput(code="", tests=None)
            return result
        except Exception as e:
            logger.error(f"Orchestration failed: {str(e)}")
            return "failed", CodeOutput(code="", tests=None)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        logger.debug(f"Starting orchestration for task={task.task_id}, stop_at={stop_at}")
        architect_key = f"Architect_{task.task_id}"
        architect = Architect(task.task_id, self.session_id, self.model_manager)
        self.add_agent(architect)
        logger.debug(f"Instantiated Architect: {architect_key} (type: {type(architect).__name__})")
        self.agent_flow.append({"agent_name": architect.name, "task_id": task.task_id,
                               "language": task.parameters.get("language", "")})

        try:
            status, plan = architect.process_task(task)  # Updated to expect two values
            logger.debug(f"{architect_key} executed, status={status}, plan={plan}")
            task.parameters[architect_key] = {"status": status, "result": plan}
            if status != "generated" or not plan or not hasattr(plan, "subtasks"):
                logger.warning(f"Invalid plan from {architect_key}, status={status}")
                return "failed", CodeOutput(code="", tests=None)
        except Exception as e:
            logger.error(f"{architect_key} failed: {str(e)}")
            task.parameters[architect_key] = {"status": "failed", "result": None}
            return "failed", CodeOutput(code="", tests=None)

        pipeline_configs = self.infer_pipelines(task, plan)
        self.pipelines[task.task_id] = []
        final_status, final_result = "failed", None

        for config in pipeline_configs:
            language = config["language"]
            output_files = config["output_files"]
            logger.debug(f"Setting up pipeline: language={language}, output_files={output_files}")
            pipeline = self.setup_pipeline(task.task_id, language, output_files)
            self.pipelines[task.task_id].append(pipeline)

            # Create subtask for pipeline
            subtask = TaskFactory.create_code_task(
                task_id=f"{task.task_id}_{language}",
                description=task.description,
                language=language,
                output_files=output_files,
                generate_tests=task.parameters.get("generate_tests", False),
                execute=task.parameters.get("execute", False),
                use_remote=True,
                dependencies=[s.task_id for s in plan.subtasks if s.parameters.get("language") == language]
            )
            subtask.parameters.update(task.parameters)
            subtask.parameters["architect_plan"] = plan

            try:
                status, result = super().orchestrate(subtask, stop_at=stop_at)
                logger.debug(f"Pipeline completed: language={language}, status={status}, "
                            f"result_type={type(result).__name__ if result else 'None'}")
                task.parameters[f"output_{language}_{'_'.join(output_files)}"] = {
                    "output_files": output_files,
                    "result": result,
                    "status": status
                }
                if status in ["generated", "tested", "executed"]:
                    final_status = status
                    final_result = result
                self.agent_flow.append({
                    "agent_name": f"Pipeline_{language}",
                    "task_id": task.task_id,
                    "language": language,
                    "output_files": output_files,
                    "status": status
                })
            except Exception as e:
                logger.error(f"Pipeline failed for {language}/{output_files}: {str(e)}")
                task.parameters[f"output_{language}_{'_'.join(output_files)}"] = {
                    "output_files": output_files,
                    "result": None,
                    "status": "failed"
                }

        if final_status == "failed" and final_result is None:
            logger.warning("All pipelines failed, returning empty output")
            final_result = CodeOutput(code="", tests=None)

        logger.debug(f"Orchestration complete: status={final_status}, result_type={type(final_result).__name__}")
        return final_status, final_result
