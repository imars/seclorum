# seclorum/agents/developer.py
from typing import Tuple, Any, List, Dict, Optional
from seclorum.agents.base import Aggregate
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

    def setup_pipeline(self, task_id: str, language: str, output_file: str) -> List[dict]:
        logger.debug(f"Setting up pipeline for task={task_id}, language={language}, output_file={output_file}")
        generator = Generator(f"{task_id}_{language}_gen", self.session_id, self.model_manager)
        tester = Tester(f"{task_id}_{language}_test", self.session_id, self.model_manager)
        executor = Executor(f"{task_id}_{language}_exec", self.session_id)
        debugger = Debugger(f"{task_id}_{language}_debug", self.session_id, self.model_manager)

        logger.debug(f"Instantiated agents: Generator={generator.name}, Tester={tester.name}, Executor={executor.name}, Debugger={debugger.name}")

        pipeline = [
            {"agent": generator, "name": generator.name, "deps": [(f"Architect_{task_id}", {"status": "planned"})], "output_file": output_file, "language": language},
            {"agent": tester, "name": tester.name, "deps": [(generator.name, {"status": "generated"})], "output_file": f"{output_file}.test", "language": language},
            {"agent": executor, "name": executor.name, "deps": [(tester.name, {"status": "tested"})], "output_file": None, "language": language},
            {"agent": debugger, "name": debugger.name, "deps": [(executor.name, {"status": "tested", "passed": False})], "output_file": output_file, "language": language},
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
        logger.debug(f"Developer processing Task {task.task_id}, language={task.parameters.get('language', '')}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        logger.debug(f"Starting orchestration for task={task.task_id}, stop_at={stop_at}")
        architect_key = f"Architect_{task.task_id}"
        architect = Architect(task.task_id, self.session_id, self.model_manager)
        self.add_agent(architect)
        logger.debug(f"Instantiated Architect: {architect_key}")
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

        # Filter pipelines by task's output_file if provided
        task_output_file = task.parameters.get("output_file", None)
        if task_output_file:
            pipeline_configs = [cfg for cfg in pipeline_configs if cfg["output_file"] == task_output_file]
            logger.debug(f"Filtered pipelines to match task output_file={task_output_file}")
        elif not pipeline_configs:
            logger.warning(f"No pipeline configs for task={task.task_id}, using default")
            pipeline_configs = self.infer_pipelines(task, "")

        # Create subtasks for each pipeline
        for config in pipeline_configs:
            language = config["language"].lower()
            output_file = config["output_file"]
            pipeline = self.setup_pipeline(task.task_id, language, output_file)
            self.pipelines[task.task_id].extend(pipeline)

        final_outputs = []
        for pipeline in self.pipelines[task.task_id]:
            agent = pipeline["agent"]
            agent_name = pipeline["name"]
            output_file = pipeline["output_file"]
            language = pipeline["language"]

            logger.debug(f"Processing agent: {agent_name} for output_file={output_file}, language={language}")
            self.agent_flow.append({"agent_name": agent_name, "task_id": task.task_id, "language": language})

            try:
                subtask = TaskFactory.create_code_task(
                    description=f"{task.description}\nFocus on generating {language} code for {output_file}",
                    language=language,
                    generate_tests=task.parameters.get("generate_tests", False),
                    execute=task.parameters.get("execute", False),
                    use_remote=task.parameters.get("use_remote", False)
                )
                subtask.parameters["output_file"] = output_file
                status, result = agent.process_task(subtask)
                logger.debug(f"{agent_name} executed, status={status}, result_type={type(result).__name__}")

                task.parameters[agent_name] = {
                    "status": status,
                    "result": result,
                    "output_file": output_file if output_file else None,
                    "language": language
                }

                if isinstance(result, CodeOutput) and result.code.strip():
                    final_outputs.append({"output_file": output_file, "code": result.code, "tests": result.tests})
                    # Save output via Agent
                    agent.save_output(subtask, result, status="generated")
                    logger.debug(f"Saved output to {output_file}")
            except Exception as e:
                logger.debug(f"{agent_name} failed: {str(e)}")
                task.parameters[agent_name] = {
                    "status": "failed",
                    "result": CodeOutput(code="", tests=None),
                    "output_file": output_file if output_file else None,
                    "language": language
                }

            if stop_at == agent_name:
                logger.debug(f"Stopping orchestration at {agent_name}")
                break

        # Combine outputs
        final_status = "generated" if final_outputs else "failed"
        final_result = CodeOutput(code="", tests=None)
        output_dir = "examples/3d_game"
        os.makedirs(output_dir, exist_ok=True)
        for output in final_outputs:
            if output["output_file"]:
                if output["output_file"].endswith(".js"):
                    final_result.code = output["code"]
                    final_result.tests = output["tests"]
                elif output["output_file"].endswith(".html"):
                    final_result.code += f"\n{output['code']}"
                # Save to examples/3d_game/
                output_path = os.path.join(output_dir, output["output_file"])
                with open(output_path, "w") as f:
                    f.write(output["code"])
                logger.debug(f"Final save to {output_path}")

        logger.debug(f"Orchestration complete: status={final_status}, outputs={[o['output_file'] for o in final_outputs if o['output_file']]}")
        return final_status, final_result
