# seclorum/models/task.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import json
import uuid
import logging

logger = logging.getLogger(__name__)

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

class TaskFactory:
    @staticmethod
    def create_code_task(
        description: str,
        language: str,
        generate_tests: bool = False,
        execute: bool = False,
        use_remote: bool = False,
        output_file: Optional[str] = None,
        task_id: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Task:
        """Create a task for code generation, testing, and execution."""
        task_id = task_id or str(uuid.uuid4())
        parameters = {
            "language": language.lower(),
            "generate_tests": generate_tests,
            "execute": execute,
            "use_remote": use_remote
        }
        if output_file:
            parameters["output_file"] = output_file
        if timeout is not None:
            parameters["timeout"] = timeout
        logger.debug(f"Creating code task: task_id={task_id}, output_file={output_file}, parameters={parameters}")
        return Task(
            task_id=task_id,
            description=description,
            parameters=parameters
        )

    @staticmethod
    def create_message_task(
        description: str,
        sender: str,
        receiver: str,
        content: str,
        task_id: Optional[str] = None
    ) -> AgentMessage:
        """Create an agent message with an embedded task."""
        task_id = task_id or str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            description=description,
            parameters={}
        )
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            task=task,
            content=content
        )
