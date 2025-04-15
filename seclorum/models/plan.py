# seclorum/models/plan.py
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from seclorum.models.task import Task

@dataclass
class Plan:
    subtasks: List[Task]
    metadata: Dict[str, Any]

    def __init__(self, subtasks: Optional[List[Task]] = None, metadata: Optional[Dict[str, Any]] = None):
        self.subtasks = subtasks or []
        self.metadata = metadata or {}
