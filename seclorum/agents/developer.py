# seclorum/agents/developer.py
from typing import Tuple, Any, List, Dict, Optional
from seclorum.agents.base import Aggregate
from seclorum.models import Task, create_model_manager, CodeOutput, TestResult
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect
from seclorum.agents.debugger import Debugger
import uuid
import logging
import re
import json

class Developer(Aggregate):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id, model_manager)
        self.name = "Developer"
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.pipelines: Dict[str, List[dict]] = {}

    def setup_pipeline(self, task_id: str, language: str, output_file: str) -> List[dict]:
        generator = Generator(f"{task_id}_{language}_gen", self.session_id, self.model_manager)
        tester = Tester(f"{task_id}_{language}_test", self.session_id, self.model_manager)
        executor = Executor(f"{task_id}_{language}_exec", self.session_id)
        debugger = Debugger(f"{task_id}_{language}_debug", self.session_id, self.model_manager)

        pipeline = [
            {"agent": generator, "name": generator.name, "deps": [(f"Architect_{task_id}", {"status": "planned"})], "output_file": output_file, "language": language},
            {"agent": tester, "name": tester.name, "deps": [(generator.name, {"status": "generated"})], "output_file": f"{output_file}.test", "language": language},
            {"agent": executor, "name": executor.name, "deps": [(tester.name, {"status": "tested"}), (generator.name, {"status": "generated"})], "output_file": None, "language": language},
            {"agent": debugger, "name": debugger.name, "deps": [(executor.name, {"status": "tested", "passed": False})], "output_file": output_file, "language": language},
        ]

        for step in pipeline:
            self.add_agent(step["agent"], step["deps"])
        return pipeline

    def infer_pipelines(self, task: Task, plan: str) -> List[Dict[str, Any]]:
        prompt = (
            f"Given the following development plan:\n{plan}\n\n"
            "Analyze the plan and identify required development pipelines for a Three.js drone racing game. "
            "Each pipeline should specify a language ('javascript' or 'html') and an output file (e.g., 'drone_game.js', 'drone_game.html'). "
            "Consider the need for JavaScript to handle game logic, scene, drones, terrain, and race mechanics, and HTML for the UI (canvas, timer, speed, standings, button). "
            "Return a JSON list of objects, each with 'language' and 'output_file'. Ensure filenames are valid without '.test' or other suffixes. "
            "Example: [{'language': 'javascript', 'output_file': 'drone_game.js'}, {'language': 'html', 'output_file': 'drone_game.html'}]"
        )
        response = self.infer(prompt, task, use_remote=task.parameters.get("use_remote", False), max_tokens=1000)
        try:
            pipelines = json.loads(response.strip())
            for p in pipelines:
                p["output_file"] = re.sub(r'\.(test|spec)$', '', p["output_file"])
            return pipelines
        except (json.JSONDecodeError, ValueError) as e:
            self.log_update(f"Failed to parse pipeline inference: {str(e)}, defaulting to JavaScript and HTML")
            return [
                {"language": "javascript", "output_file": "drone_game.js"},
                {"language": "html", "output_file": "drone_game.html"}
            ]

    def process_task(self, task: Task) -> Tuple[str, Any]:
        self.log_update(f"Developer processing Task {task.task_id}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        self.log_update(f"Starting orchestration for task {task.task_id}, stop_at={stop_at}")
        self.log_update(f"Initial task parameters: {task.parameters}")

        architect_key = f"Architect_{task.task_id}"
        architect = Architect(task.task_id, self.session_id, self.model_manager)
        self.add_agent(architect)
        try:
            status, plan = architect.process_task(task)
            self.log_update(f"{architect_key} executed, status: {status}, plan: {plan}")
            task.parameters[architect_key] = {"status": status, "result": plan}
        except Exception as e:
            self.log_update(f"{architect_key} failed: {str(e)}")
            task.parameters[architect_key] = {"status": "failed", "result": ""}
            return "failed", CodeOutput(code="", tests=None)

        pipeline_configs = self.infer_pipelines(task, plan)
        self.log_update(f"Inferred pipelines: {pipeline_configs}")
        self.pipelines[task.task_id] = []

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

            try:
                subtask = Task(
                    task_id=f"{task.task_id}_{agent_name}",
                    description=f"{task.description}\nGenerate {language} code for {output_file}",
                    parameters={**task.parameters, "language": language, "output_file": output_file}
                )
                status, result = agent.process_task(subtask)
                self.log_update(f"{agent_name} executed, status: {status}, result: {result}")
                task.parameters[agent_name] = {
                    "status": status,
                    "result": result,
                    "output_file": output_file if output_file else None,
                    "language": language
                }

                if isinstance(result, CodeOutput) and result.code.strip():
                    final_outputs.append({"output_file": output_file, "code": result.code, "tests": result.tests})
            except Exception as e:
                self.log_update(f"{agent_name} failed: {str(e)}")
                task.parameters[agent_name] = {
                    "status": "failed",
                    "result": CodeOutput(code="", tests=None),
                    "output_file": output_file if output_file else None,
                    "language": language
                }

        final_status = "generated"
        final_result = CodeOutput(code="", tests=None)
        for output in final_outputs:
            if output["output_file"] and output["output_file"].endswith(".js"):
                final_result.code = output["code"]
                final_result.tests = output["tests"]
            elif output["output_file"] and output["output_file"].endswith(".html"):
                final_result.code += f"\n<!-- HTML -->\n{output['code']}"

        if not final_result.code.strip():
            self.log_update("No valid output from pipelines")
            final_status = "failed"
            final_result = CodeOutput(code="", tests=None)

        self.log_update(f"Final result type: {type(final_result).__name__}, outputs: {[o['output_file'] for o in final_outputs if o['output_file']]}")
        return final_status, final_result
