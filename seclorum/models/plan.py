# seclorum/models/plan.py
from typing import List
from pydantic import BaseModel, validator
from seclorum.languages.enums import Language
from seclorum.models import Task  # Import Task

class Plan(BaseModel):
    subtasks: List[Task]

    @validator("subtasks")
    def validate_subtasks(cls, value):
        if not value:
            raise ValueError("Plan must include at least one subtask")
        for i, task in enumerate(value):
            if "config_output" in task.parameters.get("output_files", []) and i != len(value) - 1:
                value.append(value.pop(i))  # Move config subtask to end
        return value
