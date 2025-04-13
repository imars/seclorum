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
        self.log_update(f"Planning for task: {task.description[:100]}...")
        prompt = (
            f"Create a development plan for the following task:\n{task.description}\n\n"
            "The plan should outline the components needed for a Three.js drone racing game, including JavaScript logic (scene, camera, drones, terrain, controls, race mechanics) "
            "and HTML UI (canvas, timer, speed, standings, start/reset button). Specify that JavaScript uses the global THREE object from a CDN. "
            "Return a concise, structured plan as a string, focusing on key components and files (drone_game.js, drone_game.html)."
        )
        use_remote = task.parameters.get("use_remote", False)
        plan = self.infer(prompt, task, use_remote=use_remote, use_context=False)
        self.log_update(f"Generated plan: {plan[:100]}...")
        self.save_output(task, plan, status="planned")
        self.commit_changes(f"Planned task {task.task_id}")
        return "planned", plan

    def start(self):
        self.log_update("Starting architect")

    def stop(self):
        self.log_update("Stopping architect")
