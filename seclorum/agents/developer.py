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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Developer(Aggregate):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id, model_manager)
        self.name = "Developer"
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.pipelines: Dict[str, List[dict]] = {}
        self.agent_flow = []  # Track agents for test compatibility
        logger.debug(f"Developer initialized: session_id={session_id}")
        # Log agent classes for patch verification
        logger.debug(f"Agent classes: Architect={Architect.__name__}, Generator={Generator.__name__}, "
                     f"Tester={Tester.__name__}, Executor={Executor.__name__}, Debugger={Debugger.__name__}")

    def setup_pipeline(self, task_id: str, language: str, output_file: str) -> List[dict]:
        logger.debug(f"Setting up pipeline for task={task_id}, language={language}, output_file={output_file}")
        generator = Generator(f"{task_id}_{language}_gen", self.session_id, self.model_manager)
        tester = Tester(f"{task_id}_{language}_test", self.session_id, self.model_manager)
        executor = Executor(f"{task_id}_{language}_exec", self.session_id)
        debugger = Debugger(f"{task_id}_{language}_debug", self.session_id, self.model_manager)

        logger.debug(f"Instantiated agents: Generator={generator.name} (type: {type(generator).__name__}), "
                     f"Tester={tester.name} (type: {type(tester).__name__}), "
                     f"Executor={executor.name} (type: {type(executor).__name__}), "
                     f"Debugger={debugger.name} (type: {type(debugger).__name__})")

        pipeline = [
            {"agent": generator, "name": generator.name, "deps": [(f"Architect_{task_id}", {"status": "planned"})], "output_file": output_file, "language": language},
            {"agent": tester, "name": tester.name, "deps": [(generator.name, {"status": "generated"})], "output_file": output_file, "language": language},
            {"agent": executor, "name": executor.name, "deps": [(tester.name, {"status": "tested"})], "output_file": output_file, "language": language},
            {"agent": debugger, "name": debugger.name, "deps": [(executor.name, {"status": "executed", "passed": False})], "output_file": output_file, "language": language},
        ]

        for step in pipeline:
            self.add_agent(step["agent"], step["deps"])
            logger.debug(f"Added agent {step['name']} to pipeline")
        return pipeline

    def infer_pipelines(self, task: Task, plan: str) -> List[Dict[str, Any]]:
        logger.debug(f"Inferring pipelines for task={task.task_id}")
        prompt = (
            f"Given the following development plan:\n{plan}\n\n"
            "Analyze the plan and determine the necessary development pipelines. Each pipeline should handle a specific output file and language (javascript, html). "
            "Return a JSON list of objects, each with 'language' ('javascript' or 'html') and 'output_file' (e.g., 'drone_game.js', 'drone_game.html'). "
            "Ensure output_file is a source file, not a test file."
        )
        try:
            response = self.infer(prompt, task, use_remote=task.parameters.get("use_remote", False))
            logger.debug(f"infer_pipelines response: {response}")
            # Handle both {"pipelines": [...]} and [...] formats
            data = json.loads(response)
            pipelines = data.get("pipelines", data) if isinstance(data, dict) else data
            for p in pipelines:
                p["language"] = p["language"].lower()
                p["output_file"] = re.sub(r'\.(test|spec)$', '', p["output_file"])
                if p["language"] == "javascript" and not p["output_file"].endswith(".js"):
                    p["output_file"] += ".js"
                elif p["language"] == "html" and not p["output_file"].endswith(".html"):
                    p["output_file"] += ".html"
            logger.debug(f"Inferred pipelines: {pipelines}")
            return pipelines
        except Exception as e:
            logger.debug(f"Pipeline inference failed: {str(e)}, defaulting to JavaScript and HTML")
            return [
                {"language": "javascript", "output_file": "drone_game.js"},
                {"language": "html", "output_file": "drone_game.html"}
            ]

    def process_task(self, task: Task) -> Tuple[str, Any]:
        logger.debug(f"Developer processing Task {task.task_id}, language={task.parameters.get('language', '')}, "
                     f"parameters={task.parameters}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        logger.debug(f"Starting orchestration for task={task.task_id}, stop_at={stop_at}")
        architect_key = f"Architect_{task.task_id}"
        architect = Architect(task.task_id, self.session_id, self.model_manager)
        self.add_agent(architect)
        logger.debug(f"Instantiated Architect: {architect_key} (type: {type(architect).__name__})")
        self.agent_flow.append({"agent_name": architect.name, "task_id": task.task_id, "language": task.parameters.get("language", "")})

        try:
            status, plan = architect.process_task(task)
            logger.debug(f"{architect_key} executed, status={status}, plan={plan}")
            task.parameters[architect_key] = {"status": status, "result": plan}
        except Exception as e:
            logger.debug(f"{architect_key} failed: {str(e)}")
            task.parameters[architect_key] = {"status": "failed", "result": ""}
            return "failed", CodeOutput(code="", tests=None)

        pipeline_configs = self.infer_pipelines(task, plan)
        self.pipelines[task.task_id] = []
