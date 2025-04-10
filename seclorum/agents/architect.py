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
        plan = self.model_manager.generate(f"Create a detailed plan for: {task.description}")
        enhanced_task = Task(task_id=task.task_id, description=f"{task.description}\nPlan:\n{plan}", parameters=task.parameters)
        self.memory.save(response=f"Task plan:\n{plan}", task_id=task.task_id)
        return "planned", enhanced_task
