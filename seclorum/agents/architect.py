# seclorum/agents/architect.py
from seclorum.agents.agent import Agent
from seclorum.models import Task, Plan, create_model_manager, ModelManager
import json
import logging
import time

logger = logging.getLogger(__name__)

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager = None):
        super().__init__(f"Architect_{task_id}", session_id, model_manager)
        self.task_id = task_id
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Architect initialized for Task {task_id}, session_id={session_id}")

    def process_task(self, task: Task) -> tuple[str, Plan]:
        logger.debug(f"Processing task={task.task_id}, description={task.description[:100]}")
        start_time = time.time()
        try:
            prompt = (
                f"Task Description: {task.description}\n\n"
                "Create a plan for implementing the task. "
                "Return a JSON object with 'subtasks' (list of objects with 'description', 'language', 'output_file') "
                "and 'metadata' (object with 'version' and optional fields). "
                "Example:\n"
                '{\n  "subtasks": [\n    {"description": "Generate core logic", "language": "javascript", "output_file": "app.js"},\n'
                '    {"description": "Generate UI", "language": "html", "output_file": "index.html"}\n  ],\n'
                '  "metadata": {"version": 1}\n}'
            )
            logger.debug(f"Architect prompt: {prompt[:200]}...")
            use_remote = task.parameters.get("use_remote", False)
            raw_plan = self.infer(prompt, task, use_remote=use_remote, max_tokens=1000)
            logger.debug(f"Raw plan: {raw_plan[:200]}...")

            try:
                plan_data = json.loads(raw_plan)
                subtasks = [
                    Task(
                        task_id=f"{task.task_id}_{i}",
                        description=subtask["description"],
                        parameters={"language": subtask["language"], "output_file": subtask["output_file"]}
                    )
                    for i, subtask in enumerate(plan_data.get("subtasks", []))
                ]
                metadata = plan_data.get("metadata", {"version": 1})
                plan = Plan(subtasks=subtasks, metadata=metadata)
                logger.debug(f"Parsed plan: {len(subtasks)} subtasks, metadata={metadata}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in plan: {str(e)}, raw={raw_plan[:200]}...")
                plan = Plan(
                    subtasks=[
                        Task(
                            task_id=f"{task.task_id}_0",
                            description="Generate default JavaScript logic",
                            parameters={"language": "javascript", "output_file": "drone_game.js"}
                        )
                    ],
                    metadata={"version": 1, "error": f"Invalid JSON: {str(e)}"}
                )
                logger.debug(f"Fallback plan: {len(plan.subtasks)} subtasks")

            self.save_output(task, plan, status="planned")
            elapsed = time.time() - start_time
            logger.debug(f"Architect.process_task completed in {elapsed:.2f}s")
            self.track_flow(task, "planned", plan, use_remote)
            return "planned", plan
        except Exception as e:
            logger.error(f"Architect failed for task {task.task_id}: {str(e)}")
            plan = Plan(
                subtasks=[
                    Task(
                        task_id=f"{task.task_id}_0",
                        description="Generate default JavaScript logic",
                        parameters={"language": "javascript", "output_file": "drone_game.js"}
                    )
                ],
                metadata={"version": 1, "error": f"Processing failed: {str(e)}"}
            )
            self.save_output(task, plan, status="failed")
            elapsed = time.time() - start_time
            logger.debug(f"Architect.process_task failed in {elapsed:.2f}s")
            self.track_flow(task, "failed", plan, use_remote)
            return "failed", plan
