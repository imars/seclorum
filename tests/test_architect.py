# tests/test_architect.py
import unittest
import logging
import json
import argparse
import sys
import os
from typing import Optional
from unittest.mock import patch, Mock
from seclorum.models import Task, Plan, TaskFactory
from seclorum.agents.architect import Architect
from seclorum.models.manager import ModelManager, create_model_manager
from seclorum.agents.memory.manager import MemoryManager
import time
import requests
import uuid
import contextlib
import io
import warnings
import traceback

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="chromadb")

# Clear root logger handlers
logging.getLogger('').handlers.clear()

# Configure loggers early to suppress all non-CONVERSATION logs
pydot_logger = logging.getLogger('pydot')
pydot_logger.setLevel(logging.CRITICAL)
pydot_logger.addHandler(logging.NullHandler())
pydot_logger.propagate = False
logging.getLogger('llama_cpp').setLevel(logging.CRITICAL)
logging.getLogger('ollama').setLevel(logging.CRITICAL)
logging.getLogger('').setLevel(logging.CRITICAL)

# Context manager to suppress stdout/stderr
@contextlib.contextmanager
def suppress_output():
    stdout, stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = stdout
        sys.stderr = stderr

# Patch logging.getLogger to suppress pydot logs during import
with patch('logging.getLogger') as mock_get_logger:
    mock_logger = Mock()
    mock_logger.setLevel = Mock()
    mock_logger.addHandler = Mock()
    mock_logger.propagate = False
    mock_get_logger.side_effect = lambda name: mock_logger if name == 'pydot' else logging.getLogger(name)
    try:
        with suppress_output():
            import pydot
    except ImportError as e:
        logging.getLogger(__name__).warning(f"Failed to import pydot: {e}. Skipping pydot functionality.")
        pydot = None

# Reapply pydot suppression and log state
pydot_logger = logging.getLogger('pydot')
pydot_logger.setLevel(logging.CRITICAL)
pydot_logger.addHandler(logging.NullHandler())
pydot_logger.propagate = False
logger = logging.getLogger(__name__)
logger.debug(f"pydot logger: level={pydot_logger.level}, handlers={pydot_logger.handlers}, propagate={pydot_logger.propagate}")

# Parse custom arguments
parser = argparse.ArgumentParser(description="Test Architect with a specified model and mode", add_help=False)
parser.add_argument("--model", default="llama3.2:latest", help="Model name (e.g., qwen3:4b, gemini-1.5-flash)")
parser.add_argument("--remote", action="store_true", help="Use remote inference (Google AI Studio)")
parser.add_argument("--mock", action="store_true", default=False, help="Enable mock API mode (default: False)")
parser.add_argument("--conv", default="conversation", choices=["debug", "info", "conversation", "warning", "error", "critical"],
                    help="Set logging level (default: conversation)")
args, unittest_args = parser.parse_known_args()

# Set LOG_LEVEL based on --conv
os.environ["LOG_LEVEL"] = args.conv.upper()

class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
    def json(self):
        return self.json_data
    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"Mock error: {self.status_code}")

class TestArchitect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.args = args
        with suppress_output():
            try:
                cls.memory_manager = MemoryManager()
            except Exception as e:
                logger.error(f"Failed to initialize MemoryManager: {str(e)}\n{traceback.format_exc()}")
                raise
        cls.architects = []

    def setUp(self):
        self.session_id = f"test_session_{uuid.uuid4()}"
        self.model_name = self.args.model
        self.use_remote = self.args.remote
        self.mock_api = self.args.mock
        logger.conversation(f"Setting up test with session_id={self.session_id}, model={self.model_name}, remote={self.use_remote}, mock_api={self.mock_api}")
        self.post_patcher = None
        self.get_patcher = None
        self.outlines_patcher = None
        self.mock_plan_response = json.dumps({
            "subtasks": [
                {
                    "description": "Create HTML structure",
                    "language": "html",
                    "parameters": {"output_files": ["drone_game.html"]},
                    "dependencies": [],
                    "prompt": "Generate HTML for drone game"
                },
                {
                    "description": "Style UI",
                    "language": "css",
                    "parameters": {"output_files": ["styles.css"]},
                    "dependencies": ["Create HTML structure"],
                    "prompt": "Generate CSS for drone game"
                },
                {
                    "description": "Configure project",
                    "language": "json",
                    "parameters": {"output_files": ["package.json"]},
                    "dependencies": [],
                    "prompt": "Generate package.json"
                },
                {
                    "description": "Implement game logic",
                    "language": "javascript",
                    "parameters": {"output_files": ["game_logic.js"]},
                    "dependencies": ["Create HTML structure"],
                    "prompt": "Generate JS for drone game"
                },
                {
                    "description": "Add settings",
                    "language": "javascript",
                    "parameters": {"output_files": ["settings.js"]},
                    "dependencies": ["Create HTML structure"],
                    "prompt": "Generate JS settings"
                }
            ]
        })
        if self.mock_api:
            if self.use_remote:
                original_api_key = os.environ.get("GOOGLE_AI_STUDIO_API_KEY")
                os.environ["GOOGLE_AI_STUDIO_API_KEY"] = "x" * 39
                logger.conversation(f"Set dummy GOOGLE_AI_STUDIO_API_KEY")
                mock_post_response = {
                    "candidates": [{
                        "content": {
                            "parts": [{"text": self.mock_plan_response}]
                        }
                    }]
                }
                mock_get_response = {
                    "models": [
                        {"name": "gemini-1.5-flash", "version": "001"}
                    ]
                }
                def mock_get(*args, **kwargs):
                    logger.conversation(f"Mock GET triggered")
                    return MockResponse(mock_get_response, 200)
                def mock_post(*args, **kwargs):
                    logger.conversation(f"Mock POST triggered")
                    return MockResponse(mock_post_response, 200)
                self.post_patcher = patch('requests.post', side_effect=mock_post)
                self.get_patcher = patch('requests.get', side_effect=mock_get)
                self.post_patcher.start()
                self.get_patcher.start()
                logger.conversation("Mocking Google AI Studio API responses")
                self.original_api_key = original_api_key
            else:
                def mock_outlines_generate(*args, **kwargs):
                    logger.conversation(f"Mock OutlinesModelManager.generate triggered")
                    return self.mock_plan_response
                self.outlines_patcher = patch(
                    'seclorum.models.managers.outlines.OutlinesModelManager.generate',
                    side_effect=mock_outlines_generate
                )
                self.outlines_patcher.start()
                logger.conversation(f"Mocking OutlinesModelManager.generate for model {self.model_name}")
        memory_kwargs = {
            "base_dir": "agents/logs/conversations",
            "vector_db_path": "/var/folders/2p/jyc0xwzx5wn8tkn6032dkfth0000gn/T/chroma_db",
            "embedding_model": "nomic-embed-text:latest"
        }
        if self.use_remote:
            with suppress_output():
                try:
                    self.google_model_manager = create_model_manager(provider="google_ai_studio", model_name=self.model_name)
                except Exception as e:
                    logger.error(f"Failed to initialize Google model manager for {self.model_name}: {str(e)}\n{traceback.format_exc()}")
                    raise
            try:
                self.google_architect = Architect(
                    task_id="TestArchitectGoogle",
                    session_id=self.session_id,
                    model_manager=self.google_model_manager,
                    memory_kwargs=memory_kwargs
                )
                self.local_architects = {}
                self.architects.append(self.google_architect)
                logger.conversation(f"Initialized Google model manager for {self.model_name} (remote)")
            except Exception as e:
                logger.error(f"Failed to initialize Google Architect for {self.model_name}: {str(e)}\n{traceback.format_exc()}")
                raise
        else:
            self.google_model_manager = None
            self.google_architect = None
            self.models = ["llama3.2:latest", "qwen3:4b"] if self.model_name in ["llama3.2:latest", "qwen3:4b"] else [self.model_name]
            self.local_architects = {}
            for model_name in self.models:
                try:
                    if self.mock_api:
                        mock_model_manager = Mock(spec=ModelManager)
                        mock_model_manager.generate = Mock(side_effect=mock_outlines_generate)
                        mock_model_manager.model_name = model_name
                        mock_model_manager.provider = "outlines"
                        mock_model_manager.name = model_name  # Add name attribute
                        mock_model_manager.close = Mock()
                        mock_model_manager.should_use_remote = Mock(return_value=False)
                        mock_model_manager.remote_infer = Mock(return_value=None)
                        logger.debug(f"Mock ModelManager for {model_name}: {dir(mock_model_manager)}")
                    else:
                        with suppress_output():
                            outlines_model_manager = create_model_manager(
                                provider="outlines", model_name=model_name, use_custom_tokenizer=True
                            )
                    logger.debug(f"Creating Architect for {model_name}_custom, mock={self.mock_api}")
                    architect_custom = Architect(
                        task_id=f"TestArchitectOutlines_{model_name}_custom",
                        session_id=self.session_id,
                        model_manager=mock_model_manager if self.mock_api else outlines_model_manager,
                        memory_kwargs=memory_kwargs
                    )
                    self.local_architects[f"{model_name}_custom"] = architect_custom
                    self.architects.append(architect_custom)
                    logger.conversation(f"Initialized Outlines model manager with custom tokenizer for {model_name} (mock={self.mock_api})")
                    if self.mock_api:
                        mock_model_manager = Mock(spec=ModelManager)
                        mock_model_manager.generate = Mock(side_effect=mock_outlines_generate)
                        mock_model_manager.model_name = model_name
                        mock_model_manager.provider = "outlines"
                        mock_model_manager.name = model_name  # Add name attribute
                        mock_model_manager.close = Mock()
                        mock_model_manager.should_use_remote = Mock(return_value=False)
                        mock_model_manager.remote_infer = Mock(return_value=None)
                        logger.debug(f"Mock ModelManager for {model_name}: {dir(mock_model_manager)}")
                    else:
                        with suppress_output():
                            outlines_model_manager = create_model_manager(
                                provider="outlines", model_name=model_name, use_custom_tokenizer=False
                            )
                    logger.debug(f"Creating Architect for {model_name}_llama, mock={self.mock_api}")
                    architect_llama = Architect(
                        task_id=f"TestArchitectOutlines_{model_name}_llama",
                        session_id=self.session_id,
                        model_manager=mock_model_manager if self.mock_api else outlines_model_manager,
                        memory_kwargs=memory_kwargs
                    )
                    self.local_architects[f"{model_name}_llama"] = architect_llama
                    self.architects.append(architect_llama)
                    logger.conversation(f"Initialized Outlines model manager with llama.cpp tokenizer for {model_name} (mock={self.mock_api})")
                except Exception as e:
                    logger.error(f"Failed to initialize Outlines Architect for {model_name}: {str(e)}\n{traceback.format_exc()}")
                    self.local_architects[f"{model_name}_custom"] = None
                    self.local_architects[f"{model_name}_llama"] = None
        logger.conversation(f"TestArchitect set up with session_id={self.session_id}, model={self.model_name}, remote={self.use_remote}")

    def tearDown(self):
        if self.post_patcher:
            self.post_patcher.stop()
            logger.conversation("Stopped requests.post patcher")
        if self.get_patcher:
            self.get_patcher.stop()
            logger.conversation("Stopped requests.get patcher")
        if self.outlines_patcher:
            self.outlines_patcher.stop()
            logger.conversation("Stopped OutlinesModelManager.generate patcher")
        if hasattr(self, 'original_api_key'):
            if self.original_api_key is None:
                os.environ.pop("GOOGLE_AI_STUDIO_API_KEY", None)
            else:
                os.environ["GOOGLE_AI_STUDIO_API_KEY"] = self.original_api_key
            logger.conversation("Restored original GOOGLE_AI_STUDIO_API_KEY")

    @classmethod
    def tearDownClass(cls):
        for architect in cls.architects:
            if architect:
                architect.stop()
                if hasattr(architect, 'model') and architect.model and hasattr(architect.model, 'close'):
                    architect.model.close()
                    logger.conversation(f"Closed model manager for architect {architect.name}")
        if cls.memory_manager:
            cls.memory_manager.close()
            logger.conversation("Closed MemoryManager resources")

    def create_task(self, task_id: str, use_remote: bool = False, max_tokens: int = 8192) -> Task:
        return TaskFactory.create_code_task(
            task_id=task_id,
            description="Create a web-based JavaScript application for a drone racing game. Use Three.js for 3D rendering and simplex-noise for procedural terrain generation. Include a canvas (id='canvas'), UI controls, and ensure compatibility with modern browsers. Output files: drone_game.html, styles.css, package.json.",
            language="javascript",
            generate_tests=False,
            execute=False,
            use_remote=use_remote,
            output_files=["drone_game.html", "styles.css", "package.json"],
            max_tokens=max_tokens
        )

    def validate_plan(self, plan: Plan, task: Task) -> None:
        self.assertIsInstance(plan, Plan, f"Expected Plan object, got {type(plan).__name__}")
        self.assertTrue(plan.subtasks, "Plan must have subtasks")
        expected_files = set(task.parameters.get("output_files", []))
        generated_files = set()
        for subtask in plan.subtasks:
            output_files = subtask.parameters.get("output_files", [])
            generated_files.update(output_files)
        self.assertTrue(expected_files.issubset(generated_files), f"Expected files {expected_files} not all in generated files {generated_files}")

    def test_background_embedding(self):
        task = self.create_task("embedding_test_task", use_remote=self.use_remote, max_tokens=8192)
        logger.conversation(f"Created task for embedding test: task_id={task.task_id}")
        architect = self.google_architect if self.use_remote else self.local_architects.get(f"{self.model_name}_custom")
        if architect is None:
            self.fail(f"Architect not initialized for model {self.model_name}")
        architect.log_conversation(f"Processing embedding test task: {task.task_id}")
        for attempt in range(3):  # Retry up to 3 times
            status, result = architect.process_task(task)
            if status == "generated":
                break
            logger.conversation(f"Retry attempt {attempt + 1} for embedding test due to status: {status}")
            time.sleep(1)  # Brief delay between retries
        architect.log_conversation(f"Embedding test task result: status={status}, subtasks={len(result.subtasks) if isinstance(result, Plan) else 0}")
        self.assertEqual(status, "generated", f"Expected status 'generated', got '{status}'")
        with suppress_output():
            memory = architect.memory_manager.get_memory(architect.session_id)
            history = memory.load_history(task.task_id, architect.name)
        self.assertTrue(history, "No conversation history found")
        prompt, response, _ = history[-1]
        architect.log_conversation(f"Embedding test - Prompt: {prompt[:200]}...")
        architect.log_conversation(f"Embedding test - Response: {response[:200]}...")
        text = prompt + "\n" + response
        with suppress_output():
            similar_results = memory.find_similar(text, task.task_id, n_results=1)
        self.assertTrue(similar_results, "No embeddings found in VectorBackend")
        logger.conversation(f"Background embedding test passed: found {len(similar_results)} similar results")

    def test_drone_racing_game_plan(self):
        task = self.create_task("drone_racing_task_google", use_remote=self.use_remote, max_tokens=8192)
        logger.conversation(f"Created task for drone racing: task_id={task.task_id}")
        architect = self.google_architect if self.use_remote else self.local_architects.get(f"{self.model_name}_custom")
        if architect is None:
            self.fail(f"Architect not initialized for model {self.model_name}")
        architect.log_conversation(f"Processing drone racing task: {task.task_id}")
        for attempt in range(3):  # Retry up to 3 times
            status, result = architect.process_task(task)
            if status == "generated":
                break
            logger.conversation(f"Retry attempt {attempt + 1} for drone racing test due to status: {status}")
            time.sleep(1)  # Brief delay between retries
        architect.log_conversation(f"Drone racing task result: status={status}, subtasks={len(result.subtasks)}")
        logger.conversation(f"Task processed: status={status}, result_type={type(result).__name__}")
        self.assertEqual(status, "generated", f"Expected status 'generated', got '{status}'")
        self.assertIsInstance(result, Plan, f"Expected Plan object, got {type(result).__name__}")
        logger.conversation(f"Subtask count: {len(result.subtasks)}")
        self.validate_plan(result, task)

if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]] + unittest_args)
