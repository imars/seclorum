from seclorum.agents.base import Agent
from seclorum.models import Task, create_model_manager, ModelManager, Plan
from seclorum.models.task import TaskFactory
from typing import Tuple
import logging
import json
import uuid

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Architect_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Architect initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, Plan]:
        self.log_update(f"Planning for task: {task.description[:100]}...")
        prompt = (
            f"Create a development plan for the following task:\n{task.description}\n\n"
            "Generate a structured plan outlining components, subtasks, and output files. "
            "Return a JSON object with 'subtasks' (list of objects with 'description', 'language', and 'output_file') "
            "and 'metadata' (e.g., version, project name)."
        )
        use_remote = task.parameters.get("use_remote", False)
        plan_json = self.infer(prompt, task, use_remote=use_remote, use_context=False)
        self.log_update(f"Generated plan JSON: {plan_json[:100]}...")

        try:
            plan_data = json.loads(plan_json)
            subtasks = []
            for subtask_data in plan_data.get("subtasks", []):
                self.log_update(f"Creating subtask: {subtask_data}")
                subtask = TaskFactory.create_code_task(
                    description=subtask_data.get("description", "Unnamed subtask"),
                    language=subtask_data.get("language", "javascript"),
                    output_file=subtask_data.get("output_file", "output"),
                    generate_tests=False,
                    execute=False,
                    use_remote=use_remote,
                    task_id=str(uuid.uuid4())
                )
                subtasks.append(subtask)
            plan = Plan(
                subtasks=subtasks,
                metadata=plan_data.get("metadata", {})
            )
        except json.JSONDecodeError as e:
            self.log_update(f"Failed to parse plan JSON: {str(e)}, using fallback plan")
            plan = Plan(
                subtasks=[TaskFactory.create_code_task(
                    description=task.description,
                    language="javascript",
                    output_file="output.js",
                    generate_tests=False,
                    execute=False,
                    use_remote=use_remote,
                    task_id=str(uuid.uuid4())
                )],
                metadata={"error": "Invalid plan format", "original_task": task.description}
            )

        self.save_output(task, plan, status="planned")
        self.commit_changes(f"Planned task {task.task_id}")
        return "planned", plan

    def start(self):
        self.log_update("Starting architect")

    def stop(self):
        self.log_update("Stopping architect")
