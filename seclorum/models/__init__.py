# seclorum/models/__init__.py
from .task import (
    Task,
    TaskFactory,
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
from .manager import ModelManager, create_model_manager
from .managers.mock import MockModelManager
from .managers.ollama import OllamaModelManager
from .managers.llama_cpp import LlamaCppModelManager
from .managers.google import GoogleModelManager
from .managers.outlines import OutlinesModelManager

__all__ = [
    "Task",
    "Plan",
    "TaskFactory",
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
    "CodeResult",
    "ModelManager",
    "create_model_manager",
    "OllamaModelManager",
    "LlamaCppModelManager",
    "GoogleModelManager",
    "MockModelManager",
    "OutlinesModelManager"
]
