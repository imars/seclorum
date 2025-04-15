# seclorum/models/__init__.py
from .task import (
    Task,
    AgentMessage,
    FileListToolInput,
    FileListToolOutput,
    TrainingSample,
    PredictionInput,
    PredictionOutput,
    OutsourcedTaskInput,
    OutsourcedTaskOutput
)
from .code import CodeOutput, TestResult, CodeResult
from .plan import Plan
from .manager import create_model_manager, ModelManager, OllamaModelManager, MockModelManager

__all__ = [
    "Task",
    "Plan",
    "AgentMessage",
    "FileListToolInput",
    "FileListToolOutput",
    "TrainingSample",
    "PredictionInput",
    "PredictionOutput",
    "OutsourcedTaskInput",
    "OutsourcedTaskOutput",
    "CodeOutput",
    "TestResult",
    "create_model_manager",
    "ModelManager",
    "OllamaModelManager",
    "MockModelManager"
]
