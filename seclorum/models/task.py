# seclorum/models.py
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
    dependencies: Optional[List[str]] = Field(default_factory=list)
    prompt: Optional[str] = None

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
        output_files: Optional[List[str]] = None,
        task_id: Optional[str] = None,
        timeout: Optional[int] = None,
        dependencies: Optional[List[str]] = None,
        prompt: Optional[str] = None,
        max_tokens: Optional[int] = None  # Added parameter
    ) -> Task:
        """Create a task for code generation, testing, and execution."""
        task_id = task_id or str(uuid.uuid4())
        parameters = {
            "language": language.lower(),
            "generate_tests": generate_tests,
            "execute": execute,
            "use_remote": use_remote
        }
        if output_files:
            parameters["output_files"] = output_files
        if timeout is not None:
            parameters["timeout"] = timeout
        if max_tokens is not None:
            parameters["max_tokens"] = max_tokens
        logger.debug(f"Creating code task: task_id={task_id}, output_files={output_files}, parameters={parameters}, dependencies={dependencies}, prompt={prompt}")
        return Task(
            task_id=task_id,
            description=description,
            parameters=parameters,
            dependencies=dependencies or [],
            prompt=prompt
        )

    @staticmethod
    def create_message_task(
        description: str,
        sender: str,
        receiver: str,
        content: str,
        task_id: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> AgentMessage:
        """Create an agent message with an embedded task."""
        task_id = task_id or str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            description=description,
            parameters={},
            prompt=prompt
        )
        return AgentMessage(
            sender=sender,
            receiver=receiver,
            task=task,
            content=content
        )
