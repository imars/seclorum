# seclorum/agents/architect.py
from typing import Tuple
from seclorum.agents.base import Agent
from seclorum.models import Task

class Architect(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager):
        super().__init__(f"Architect_{task_id}", session_id)
        self.task_id = task_id
        self.model_manager = model_manager
        self.log_update(f"Architect initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, Task]:
        self.log_update(f"Planning Task {task.task_id}: {task.description}")
        prompt = f"Create a detailed plan for the following task: {task.description}"
        use_remote = task.parameters.get("use_remote", None)
        if use_remote:
            self.log_update("Using remote inference (Google AI Studio)")
        else:
            self.log_update("Using local inference (Ollama)")
        plan = self.infer(prompt, use_remote=use_remote)
        task.description = f"{task.description}\nPlan:\n{plan}"
        self.memory.save(response=task, task_id=task.task_id)
        return "planned", task
