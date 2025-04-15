from seclorum.agents.base import Agent
from seclorum.models import Task, Plan, create_model_manager, ModelManager
from typing import Tuple, List
import json
import logging
import uuid

logger = logging.getLogger(__name__)

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager = None):
        super().__init__(f"Architect_{task_id}", session_id, model_manager)
        self.task_id = task_id
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Architect initialized for task {task_id}, session_id={session_id}")

    def process_task(self, task: Task) -> Tuple[str, Plan]:
        logger.debug(f"Processing task {task.task_id}: description={task.description[:100]}...")
        try:
            prompt = (
                f"Create a plan for the following task:\n{task.description}\n\n"
                "Generate a JSON object with:\n"
                "- 'subtasks': List of subtasks, each with 'description' (string), 'language' (e.g., 'javascript', 'html'), and 'output_file' (filename).\n"
                "- 'metadata': Optional dictionary with additional info (e.g., version, project).\n"
                "Return only the JSON string, no markdown or explanations."
            )
            use_remote = task.parameters.get("use_remote", False)
            raw_plan = self.infer(prompt, task, use_remote=use_remote, max_tokens=2000)
            logger.debug(f"Raw plan: {raw_plan[:200]}...")

            try:
                plan_data = json.loads(raw_plan)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse plan JSON: {str(e)}, raw_plan={raw_plan[:200]}...")
                plan_data = {
                    "subtasks": [
                        {
                            "description": "Generate default code",
                            "language": "javascript",
                            "output_file": "app.js"
                        }
                    ],
                    "metadata": {"version": 1, "error": "Invalid JSON fallback"}
                }

            subtasks = []
            for subtask_data in plan_data.get("subtasks", []):
                subtask_id = str(uuid.uuid4())
                description = subtask_data.get("description", "")
                language = subtask_data.get("language", "javascript")
                output_file = subtask_data.get("output_file", "output")
                subtask = Task(
                    task_id=subtask_id,
                    description=description,
                    parameters={"language": language, "output_file": output_file}
                )
                subtasks.append(subtask)
                logger.debug(f"Created subtask {subtask_id}: output_file={output_file}")

            metadata = plan_data.get("metadata", {})
            plan = Plan(subtasks=subtasks, metadata=metadata)
            logger.debug(f"Generated plan with {len(subtasks)} subtasks: metadata={metadata}")

            self.save_output(task, plan, status="planned")
            self.commit_changes(f"Created plan for task {task.task_id}")
            self.track_flow(task, "planned", plan, use_remote)
            return "planned", plan
        except Exception as e:
            logger.error(f"Planning failed for task {task.task_id}: {str(e)}")
            default_plan = Plan(
                subtasks=[
                    Task(
                        task_id=str(uuid.uuid4()),
                        description="Generate default code",
                        parameters={"language": "javascript", "output_file": "app.js"}
                    )
                ],
                metadata={"version": 1, "error": str(e)}
            )
            self.track_flow(task, "failed", default_plan, use_remote)
            return "failed", default_plan
