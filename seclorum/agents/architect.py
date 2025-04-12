# seclorum/agents/architect.py
from seclorum.agents.base import Agent
from seclorum.models import Task, create_model_manager, ModelManager
from typing import Tuple
import logging

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Architect_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Architect initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, str]:
        self.log_update(f"Planning for task: {task.description}")
        prompt = (
            f"Create a detailed plan for the following task: {task.description}\n"
            "Return only the plan as a concise, structured text (e.g., numbered list or bullet points), "
            "without generating code, comments, or explanations."
        )
        plan = self.infer(prompt, task, use_remote=task.parameters.get("use_remote", False), use_context=False)
        plan = plan.strip()
        self.log_update(f"Generated plan:\n{plan}")
        self.save_output(task, plan, status="planned")
        self.commit_changes(f"Planned task {task.task_id}")
        return "planned", plan

    def start(self):
        self.log_update("Starting architect")

    def stop(self):
        self.log_update("Stopping architect")
