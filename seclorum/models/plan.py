# seclorum/models/plan.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from enum import Enum

class Language(str, Enum):
    html = "html"
    css = "css"
    javascript = "javascript"
    json = "json"
    text = "text"

class Task(BaseModel):
    description: str
    language: Language
    parameters: Dict[str, Any]  # Flexible dict for output_files, etc.
    dependencies: List[str]
    prompt: str

class Plan(BaseModel):
    subtasks: List[Task]
    metadata: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True
