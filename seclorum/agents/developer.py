# seclorum/agents/developer.py
from typing import Tuple, Any, List, Dict, Optional
from seclorum.agents.aggregate import Aggregate
from seclorum.models import Task, create_model_manager, CodeOutput, CodeResult
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
        logger.debug(f"Developer initialized: session_id={session_id}")
        logger.debug(f"Agent classes: Architect={Architect.__name__}, Generator={Generator.__name__}, "
                     f"Tester={Tester.__name__}, Executor={Executor.__name__}, Debugger={Debugger.__name__}")

    def setup_pipeline(self, task_id: str, language: str, output_file: str) -> List[dict]:
        logger.debug(f"Setting up pipeline for task={task_id}, language={language}, output_file={output_file}")
        generator = Generator(f"{task_id}_{language}_gen", self.session_id, self.model_manager)
        tester = Tester(f"{task_id}_{language}_test", self.session_id, self.model_manager)
        executor = Executor(f"{task_id}_{language}_exec", self.session_id)
        debugger = Debugger(f"{task_id}_{language}_debug", self.session_id, self.model_manager)

        logger.debug(f"Instantiated agents: Generator={generator.name}, Tester={tester.name}, "
                     f"Executor={executor.name}, Debugger={debugger.name}")

        pipeline = [
            {"agent": generator, "name": generator.name, "deps": [(f"Architect_{task_id}", {"status": "planned"})],
             "output_file": output_file, "language": language},
            {"agent": tester, "name": tester.name, "deps": [(generator.name, {"status": "generated"})],
             "output_file": output_file, "language": language},
            {"agent": executor, "name": executor.name, "deps": [(generator.name, {"status": "generated"})],
             "output_file": output_file, "language": language},
            {"agent": debugger, "name": debugger.name, "deps": [(executor.name, {"status": "tested", "passed": False})],
             "output_file": output_file, "language": language},
        ]

        for step in pipeline:
            self.add_agent(step["agent"], step["deps"])
            logger.debug(f"Added agent {step['name']} to pipeline")
        return pipeline

    @timeout_decorator.timeout(30, timeout_exception=TimeoutError)
    def infer_pipelines(self, task: Task, plan: Any) -> List[Dict[str, Any]]:
        logger.debug(f"Inferring pipelines for task={task.task_id}")
        prompt = (
            f"Given the following development plan:\n{plan}\n\n"
            "Analyze the plan and determine the necessary development pipelines. Each pipeline should handle a specific output file and language (javascript, html). "
            "Return a JSON list of objects, each with 'language' ('javascript' or 'html') and 'output_file' (e.g., 'drone_game.js', 'drone_game.html'). "
            "Ensure output_file is a source file, not a test file. Example:\n"
            '[{"language": "javascript", "output_file": "drone_game.js"}, {"language": "html", "output_file": "drone_game.html"}]'
        )
        try:
            response = self.infer(prompt, task, use_remote=task.parameters.get("use_remote", True))
            logger.debug(f"infer_pipelines response: {response[:200]}...")
            cleaned_response = re.sub(r'^```json\s*|\s*```$', '', response, flags=re.MULTILINE).strip()
            try:
                data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parsing failed: {str(e)}, trying to fix")
                # Attempt to fix common JSON issues
                cleaned_response = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned_response)
                cleaned_response = re.sub(r',\s*]', ']', cleaned_response)
                cleaned_response = re.sub(r',\s*}', '}', cleaned_response)
                data = json.loads(cleaned_response)
            pipelines = data.get("pipelines", data) if isinstance(data, dict) else data
            if not isinstance(pipelines, list):
                raise ValueError("Pipelines must be a list")
            for p in pipelines:
                if not all(k in p for k in ["language", "output_file"]):
                    raise ValueError("Each pipeline must have 'language' and 'output_file'")
                p["language"] = p["language"].lower()
                p["output_file"] = re.sub(r'\.(test|spec)\b', '', p["output_file"])
                if p["language"] == "javascript" and not p["output_file"].endswith(".js"):
                    p["output_file"] += ".js"
                elif p["language"] == "html" and not p["output_file"].endswith(".html"):
                    p["output_file"] += ".html"
            logger.debug(f"Inferred pipelines: {pipelines}")
            return pipelines
        except (json.JSONDecodeError, ValueError, TimeoutError) as e:
            logger.error(f"Pipeline inference failed: {str(e)}, defaulting to JavaScript and HTML")
            return [
                {"language": "javascript", "output_file": "drone_game.js"},
                {"language": "html", "output_file": "drone_game.html"}
            ]

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
            status, plan = architect.process_task(task)
            logger.debug(f"{architect_key} executed, status={status}, plan={plan}")
            task.parameters[architect_key] = {"status": status, "result": plan}
            if status != "planned" or not plan or not hasattr(plan, "subtasks"):
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
            output_file = config["output_file"]
            logger.debug(f"Setting up pipeline: language={language}, output_file={output_file}")
            pipeline = self.setup_pipeline(task.task_id, language, output_file)
            self.pipelines[task.task_id].append(pipeline)

            # Create subtask for pipeline
            subtask = TaskFactory.create_code_task(
                task_id=f"{task.task_id}_{language}",
                description=task.description,
                language=language,
                output_file=output_file,
                generate_tests=task.parameters.get("generate_tests", False),
                execute=task.parameters.get("execute", False),
                use_remote=True
            )
            subtask.parameters.update(task.parameters)
            subtask.parameters["architect_plan"] = plan
            subtask.parameters["output_file"] = output_file

            try:
                status, result = super().orchestrate(subtask, stop_at=stop_at)
                logger.debug(f"Pipeline completed: language={language}, status={status}, "
                            f"result_type={type(result).__name__ if result else 'None'}")
                task.parameters[f"output_{language}_{output_file}"] = {
                    "output_file": output_file,
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
                    "output_file": output_file,
                    "status": status
                })
            except Exception as e:
                logger.error(f"Pipeline failed for {language}/{output_file}: {str(e)}")
                task.parameters[f"output_{language}_{output_file}"] = {
                    "output_file": output_file,
                    "result": None,
                    "status": "failed"
                }

        if final_status == "failed" and final_result is None:
            logger.warning("All pipelines failed, returning empty output")
            final_result = CodeOutput(code="", tests=None)

        logger.debug(f"Orchestration complete: status={final_status}, result_type={type(final_result).__name__}")
        return final_status, final_result
