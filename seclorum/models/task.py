# seclorum/models/task.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json

class Task(BaseModel):
    task_id: str
    description: str
    parameters: Optional[Dict] = Field(default_factory=dict)

    def to_json(self):
        return self.model_dump_json()

    @classmethod
    def from_json(cls, json_str):
        return cls.model_validate(json.loads(json_str))

class AgentMessage(BaseModel):
    sender: str
    receiver: str
    task: Task
    content: str

class FileListToolInput(BaseModel):
    directory: str = Field(default=".")

class FileListToolOutput(BaseModel):
    files: List[str]

class TrainingSample(BaseModel):
    prompt: str
    response: str

class PredictionInput(BaseModel):
    prompt: str

class PredictionOutput(BaseModel):
    response: str

class OutsourcedTaskInput(BaseModel):
    query: str
    context: Optional[str] = None

class OutsourcedTaskOutput(BaseModel):
    result: str
    confidence: float = Field(ge=0.0, le=1.0)
