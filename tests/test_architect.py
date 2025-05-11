# tests/test_architect.py
import unittest
import logging
import json
import argparse
from typing import Optional
from unittest.mock import patch
from seclorum.models import Task, Plan, TaskFactory
from seclorum.agents.architect import Architect
from seclorum.models import create_model_manager
from seclorum.agents.memory.manager import MemoryManager
import time
import os
import requests
import uuid

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
        parser = argparse.ArgumentParser(description="Test Architect with a specified model and mode")
        parser.add_argument("--model", default="llama3.2:latest", help="Model name (e.g., qwen3:4b, gemini-1.5-flash)")
        parser.add_argument("--remote", action="store_true", help="Use remote inference (Google AI Studio)")
        cls.args, _ = parser.parse_known_args()
        cls.memory_manager = MemoryManager()
        cls.architects = []

    def setUp(self):
        self.session_id = f"test_session_{uuid.uuid4()}"
        self.model_name = self.args.model
        self.use_remote = self.args.remote
        self.mock_api = os.getenv("MOCK_API") == "true"
        self.patcher = None
        if self.mock_api and self.use_remote:
            mock_response = {
                "candidates": [{"content": {"parts": [{"text": '{"subtasks": [{"description": "Create HTML structure", "language": "html", "parameters": {"output_files": ["drone_game.html"]}, "dependencies": [], "prompt": "Generate HTML for drone game"}, {"description": "Style UI", "language": "css", "parameters": {"output_files": ["styles.css"]}, "dependencies": ["Create HTML structure"], "prompt": "Generate CSS for drone game"}, {"description": "Configure project", "language": "json", "parameters": {"output_files": ["package.json"]}, "dependencies": [], "prompt": "Generate package.json"}, {"description": "Implement game logic", "language": "javascript", "parameters": {"output_files": ["game_logic.js"]}, "dependencies": ["Create HTML structure"], "prompt": "Generate JS for drone game"}, {"description": "Add settings", "language": "javascript", "parameters": {"output_files": ["settings.js"]}, "dependencies": ["Create HTML structure"], "prompt": "Generate JS settings"}]}'}]}}]
            }
            self.patcher = patch('requests.post', return_value=MockResponse(mock_response, 200))
            self.patcher.start()
            logger.info("Mocking Google AI Studio API responses")
        if self.use_remote:
            self.google_model_manager = create_model_manager(provider="google_ai_studio", model_name=self.model_name)
            self.google_architect = Architect(
                task_id="TestArchitectGoogle",
                session_id=self.session_id,
                model_manager=self.google_model_manager,
                memory_manager=self.memory_manager
            )
            self.local_architects = {}
            self.architects.append(self.google_architect)
            logger.info(f"Initialized Google model manager for {self.model_name} (remote)")
        else:
            self.google_model_manager = None
            self.google_architect = None
            self.models = ["llama3.2:latest", "qwen3:4b"] if self.model_name in ["llama3.2:latest", "qwen3:4b"] else [self.model_name]
            self.local_architects = {}
            for model_name in self.models:
                try:
                    outlines_model_manager = create_model_manager(
                        provider="outlines", model_name=model_name, use_custom_tokenizer=True
                    )
                    architect = Architect(
                        task_id=f"TestArchitectOutlines_{model_name}_custom",
                        session_id=self.session_id,
                        model_manager=outlines_model_manager,
                        memory_manager=self.memory_manager
                    )
                    self.local_architects[f"{model_name}_custom"] = architect
                    self.architects.append(architect)
                    logger.info(f"Initialized Outlines model manager with custom tokenizer for {model_name}")
                    outlines_model_manager = create_model_manager(
                        provider="outlines", model_name=model_name, use_custom_tokenizer=False
                    )
                    architect = Architect(
                        task_id=f"TestArchitectOutlines_{model_name}_llama",
                        session_id=self.session_id,
                        model_manager=outlines_model_manager,
                        memory_manager=self.memory_manager
                    )
                    self.local_architects[f"{model_name}_llama"] = architect
                    self.architects.append(architect)
                    logger.info(f"Initialized Outlines model manager with llama.cpp tokenizer for {model_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize Outlines model manager for {model_name}: {str(e)}")
                    self.local_architects[f"{model_name}_custom"] = None
                    self.local_architects[f"{model_name}_llama"] = None
        logger.info("TestArchitect set up with session_id=%s, model=%s, remote=%s", self.session_id, self.model_name, self.use_remote)

    def tearDown(self):
        if self.patcher:
            self.patcher.stop()
        logger.info("Test case completed, deferring cleanup to tearDownClass")

    @classmethod
    def tearDownClass(cls):
        for architect in cls.architects:
            if architect:
                architect.stop()
                if architect.model_manager and hasattr(architect.model_manager, 'close'):
                    architect.model_manager.close()
        cls.memory_manager.stop()
        logger.info("All architects and MemoryManager stopped")

    def normalize_plan_json(self, raw_plan: str) -> str:
        if not raw_plan:
            logger.warning("Raw plan is empty")
            return json.dumps({"subtasks": []})
        try:
            data = json.loads(raw_plan)
            if self.use_remote and "plan" in data and "tasks" in data["plan"]:
                data = {"subtasks": data["plan"]["tasks"]}
                return json.dumps(data, ensure_ascii=True)
            return raw_plan
        except json.JSONDecodeError:
            logger.warning("Failed to normalize JSON output; returning fallback")
            return json.dumps({"subtasks": []})

    def validate_plan(self, status, result, raw_plan, task, expected_provider, model_name):
        self.assertEqual(status, "generated", f"Expected status 'generated', got '{status}'")
        self.assertIsInstance(result, Plan, f"Expected Plan object, got {type(result).__name__}")
        self.assertTrue(hasattr(result, "subtasks"), "Plan must have 'subtasks' attribute")
        self.assertIsInstance(result.subtasks, list, "Subtasks must be a list")
        self.assertGreaterEqual(len(result.subtasks), 5, "Plan must include at least 5 subtasks")
        self.assertLessEqual(len(result.subtasks), 10, "Plan must include at most 10 subtasks")
        logger.info("Subtask count: %d", len(result.subtasks))
        output_files = [f for subtask in result.subtasks for f in subtask.parameters.get("output_files", [])]
        required_files = task.parameters.get("output_files", [])
        for required_file in required_files:
            self.assertIn(required_file, output_files, f"Plan must include '{required_file}' output file")
        self.assertTrue(any("settings.js" in subtask.parameters.get("output_files", []) for subtask in result.subtasks),
                        "Plan must include a settings.js file (mapped from config_output)")
        languages = set()
        task_ids = {subtask.task_id for subtask in result.subtasks}
        has_multiple_files = False
        for subtask in result.subtasks:
            self.assertTrue(subtask.description, "Subtask must have a non-empty description")
            self.assertIsInstance(subtask.parameters, dict, "Subtask parameters must be a dictionary")
            self.assertIn("output_files", subtask.parameters, "Subtask must specify 'output_files'")
            output_files = subtask.parameters.get("output_files", [])
            self.assertTrue(output_files, "Subtask must have non-empty 'output_files' list")
            if len(output_files) > 1:
                has_multiple_files = True
            language = subtask.parameters.get("language", "").lower()
            self.assertTrue(language, "Subtask must specify a language")
            self.assertNotEqual(language, "none", "Subtask language must not be 'none'")
            languages.add(language)
            if language == "css":
                self.assertTrue(all(f.endswith(".css") for f in output_files),
                               f"CSS subtask must output to .css files, got {output_files}")
            for dep_id in subtask.dependencies:
                self.assertIn(dep_id, task_ids, f"Dependency {dep_id} must be a valid subtask task_id")
            self.assertTrue(subtask.prompt, f"Subtask must have a non-empty prompt")
        self.assertTrue(has_multiple_files, "At least one subtask must have multiple output files")
        self.assertGreaterEqual(len(languages), 3, "Plan must include at least 3 pipelines")
        self.assertIn("html", languages, "Plan must include an HTML pipeline")
        self.assertIn("css", languages, "Plan must include a CSS pipeline")
        self.assertIn("javascript", languages, "Plan must include a JavaScript pipeline")
        architect = self.local_architects.get(model_name, self.google_architect)
        history = architect.memory_manager.load_history(task.task_id, architect.name, architect.session_id)
        retry_count = sum(1 for entry in history if "Inference attempt" in str(entry))
        logger.info("Retry count for %s: %d", model_name, retry_count)
        self.assertLessEqual(retry_count, 2, "Outlines should require at most 2 retries")
        try:
            plan_json = json.dumps({
                "subtasks": [
                    {
                        "task_id": subtask.task_id,
                        "description": subtask.description,
                        "parameters": subtask.parameters,
                        "dependencies": subtask.dependencies,
                        "prompt": subtask.prompt
                    } for subtask in result.subtasks
                ]
            }, indent=2)
            logger.info("Plan JSON: %s", plan_json[:200])
        except json.JSONDecodeError as e:
            self.fail(f"Plan is not JSON-serializable: {str(e)}")
        print("\n=== Raw Plan Output ===")
        try:
            parsed_plan = json.loads(raw_plan)
            print(json.dumps(parsed_plan, indent=2))
        except json.JSONDecodeError:
            logger.error("Raw plan is not valid JSON")
            print(raw_plan)
        print("======================")

    def create_task(self, task_id: str, use_remote: bool, max_tokens: Optional[int] = None) -> Task:
        return TaskFactory.create_code_task(
            task_id=task_id,
            description=(
                "Create a web-based JavaScript application for a drone racing game. "
                "Use Three.js for 3D rendering and simplex-noise for procedural terrain generation. "
                "Include a canvas (id='canvas'), UI with timer (span#timer), speed (span#speed), "
                "standings (table#standings), and start/reset button (button#startReset). "
                "Generate modular components, UI structure in 'drone_game.html', styling in 'styles.css', "
                "and configuration in 'package.json'. "
                "Include an infinite tiled scrolling terrain and a background resource loader. "
                "Reference external resources (e.g., skybox images) without generating them. "
                "Features: user controls, AI components, collision detection, standings tracking, skybox, visual effects."
            ),
            language="javascript",
            generate_tests=False,
            execute=False,
            use_remote=use_remote,
            output_files=["drone_game.html", "styles.css", "package.json"],
            max_tokens=max_tokens
        )

    def test_tokenization_error_handling(self):
        if self.use_remote:
            self.skipTest("Tokenization error handling test is for local models only")
        for model_name, architect in self.local_architects.items():
            if architect is None:
                logger.warning(f"Skipping test for {model_name} due to initialization failure")
                continue
            with self.subTest(model_name=model_name):
                start_time = time.time()
                task = self.create_task(f"tokenization_error_task_{model_name}", use_remote=False, max_tokens=4096)
                logger.info("Created task for tokenization error test: task_id=%s, model=%s", task.task_id, model_name)
                if "llama" in model_name:
                    with patch('llama_cpp.Llama.tokenize') as mock_tokenize:
                        mock_tokenize.side_effect = RuntimeError("Cannot convert token ` �` (29333) to bytes: �")
                        status, result = architect.process_task(task)
                else:
                    status, result = architect.process_task(task)
                logger.info("Task processed: status=%s, result_type=%s, duration=%s", status, type(result).__name__, time.time() - start_time)
                self.assertEqual(status, "generated", f"Expected status 'generated', got '{status}'")
                self.assertIsInstance(result, Plan, f"Expected Plan object, got {type(result).__name__}")
                self.assertTrue(result.subtasks, "Plan must have subtasks")
                self.assertTrue(any("settings.js" in subtask.parameters.get("output_files", []) for subtask in result.subtasks),
                               "Plan must include a settings.js file (mapped from config_output)")
                history = architect.memory_manager.load_history(task.task_id, architect.name, architect.session_id)
                retry_count = sum(1 for entry in history if "Inference attempt" in str(entry))
                self.assertLessEqual(retry_count, 5, f"Expected at most 5 retries, got {retry_count}")
                if "llama" in model_name:
                    cache_clear_logs = [entry for entry in history if "Outlines cache cleared successfully" in str(entry)]
                    self.assertTrue(cache_clear_logs, "Cache should have been cleared for llama.cpp tokenizer error")
                else:
                    tokenizer_logs = [entry for entry in history if "Custom tokenizer cleaned text" in str(entry)]
                    self.assertTrue(tokenizer_logs, "Custom tokenizer should have been used for problematic model")
                logger.info("Tokenization error handling tested: %d retries, %d subtasks", retry_count, len(result.subtasks))

    def test_drone_racing_game_plan_local(self):
        if self.use_remote:
            self.skipTest("Local plan test is for local models only")
        for model_name, architect in self.local_architects.items():
            if architect is None:
                logger.warning(f"Skipping test for {model_name} due to initialization failure")
                continue
            with self.subTest(model_name=model_name):
                task = self.create_task(f"drone_racing_task_{model_name}", use_remote=False, max_tokens=4096)
                logger.info("Created task: task_id=%s, model=%s", task.task_id, model_name)
                status, result = architect.process_task(task)
                raw_plan = self.normalize_plan_json(json.dumps({"subtasks": [
                    {
                        "task_id": s.task_id,
                        "description": s.description,
                        "parameters": s.parameters,
                        "dependencies": s.dependencies,
                        "prompt": s.prompt
                    } for s in result.subtasks
                ]}))
                logger.info("Task processed: status=%s, result_type=%s", status, type(result).__name__)
                self.validate_plan(status, result, raw_plan, task, expected_provider="outlines", model_name=model_name)

    def test_drone_racing_game_plan(self):
        task = self.create_task("drone_racing_task_google", use_remote=self.use_remote, max_tokens=8192)
        logger.info("Created task: task_id=%s", task.task_id)
        architect = self.google_architect if self.use_remote else self.local_architects.get(f"{self.model_name}_custom")
        if architect is None:
            self.fail(f"Architect not initialized for model {self.model_name}")
        status, result = architect.process_task(task)
        logger.debug(f"Raw inference output: {json.dumps({'subtasks': [{'task_id': s.task_id} for s in result.subtasks]})}")
        raw_plan = self.normalize_plan_json(json.dumps({"subtasks": [
            {
                "task_id": s.task_id,
                "description": s.description,
                "parameters": s.parameters,
                "dependencies": s.dependencies,
                "prompt": s.prompt
            } for s in result.subtasks
        ]}))
        logger.info("Task processed: status=%s, result_type=%s", status, type(result).__name__)
        self.validate_plan(
            status, result, raw_plan, task,
            expected_provider="google_ai_studio" if self.use_remote else "outlines",
            model_name=self.model_name
        )

    def test_compare_local_and_remote_plans(self):
        if self.use_remote:
            self.skipTest("Comparison test requires local models")
        local_plans = {}
        for model_name, architect in self.local_architects.items():
            if architect is None:
                logger.warning(f"Skipping test for {model_name} due to initialization failure")
                continue
            task = self.create_task(f"drone_racing_task_{model_name}", use_remote=False, max_tokens=4096)
            status, result = architect.process_task(task)
            raw_plan = self.normalize_plan_json(json.dumps({"subtasks": [
                {
                    "task_id": s.task_id,
                    "description": s.description,
                    "parameters": s.parameters,
                    "dependencies": s.dependencies,
                    "prompt": s.prompt
                } for s in result.subtasks
            ]}))
            self.assertEqual(status, "generated", f"Local plan generation failed for {model_name}")
            logger.info("Local plan processed: task_id=%s, subtask_count=%d", task.task_id, len(result.subtasks))
            local_plans[model_name] = (task, result, raw_plan)
        remote_task = self.create_task("drone_racing_task_google", use_remote=True, max_tokens=8192)
        remote_status, remote_result = self.google_architect.process_task(remote_task)
        remote_raw_plan = self.normalize_plan_json(json.dumps({"subtasks": [
            {
                "task_id": s.task_id,
                "description": s.description,
                "parameters": s.parameters,
                "dependencies": s.dependencies,
                "prompt": s.prompt
            } for s in remote_result.subtasks
        ]}))
        self.assertEqual(remote_status, "generated", "Remote plan generation failed")
        logger.info("Remote plan processed: task_id=%s, subtask_count=%d", remote_task.task_id, len(remote_result.subtasks))
        for model_name, (local_task, local_result, local_raw_plan) in local_plans.items():
            with self.subTest(model_name=model_name):
                local_history = self.local_architects[model_name].memory_manager.load_history(
                    local_task.task_id, self.local_architects[model_name].name, self.local_architects[model_name].session_id
                )
                remote_history = self.google_architect.memory_manager.load_history(
                    remote_task.task_id, self.google_architect.name, self.google_architect.session_id
                )
                self.assertTrue(local_history, f"Local plan not found in Memory for {model_name}")
                self.assertTrue(remote_history, "Remote plan not found in Memory")
                local_prompt, local_response = local_history[-1][:2]
                remote_prompt, remote_response = remote_history[-1][:2]
                logger.debug("Local response (%s): %s", model_name, local_response[:200])
                try:
                    local_plan = json.loads(local_response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse local plan for {model_name}: {str(e)}")
                    self.fail(f"Failed to parse local plan: {str(e)}")
                try:
                    remote_plan = json.loads(remote_response)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse remote plan: {str(e)}")
                    self.fail(f"Failed to parse remote plan: {str(e)}")
                local_subtasks = local_plan.get("subtasks", [])
                remote_subtasks = remote_plan.get("subtasks", [])
                self.assertGreaterEqual(len(local_subtasks), 5, f"Local plan ({model_name}) has too few subtasks")
                self.assertGreaterEqual(len(remote_subtasks), 5, "Remote plan has too few subtasks")
                logger.info("Local plan (%s) subtasks: %d, Remote plan subtasks: %d", model_name, len(local_subtasks), len(remote_subtasks))
                local_files = set(f for s in local_subtasks for f in s.get("parameters", {}).get("output_files", []))
                remote_files = set(f for s in remote_subtasks for f in s.get("parameters", {}).get("output_files", []))
                common_files = local_files.intersection(remote_files)
                self.assertTrue(common_files, f"No common output files between local ({model_name}) and remote plans")
                logger.info("Common output files (%s): %s", model_name, common_files)
                local_languages = set(s.get("language", "").lower() for s in local_subtasks)
                remote_languages = set(s.get("language", "").lower() for s in remote_subtasks)
                common_languages = local_languages.intersection(remote_languages)
                self.assertTrue(common_languages, f"No common languages between local ({model_name}) and remote plans")
                self.assertIn("html", common_languages, "HTML missing in common languages")
                self.assertIn("css", common_languages, "CSS missing in common languages")
                self.assertIn("javascript", common_languages, "JavaScript missing in common languages")
                logger.info("Common languages (%s): %s", model_name, common_languages)
                local_deps = sum(len(s.get("dependencies", [])) for s in local_subtasks)
                remote_deps = sum(len(s.get("dependencies", [])) for s in remote_subtasks)
                self.assertGreater(local_deps, 0, f"Local plan ({model_name}) has no dependencies")
                self.assertGreater(remote_deps, 0, "Remote plan has no dependencies")
                logger.info("Local plan (%s) dependencies: %d, Remote plan dependencies: %d", model_name, local_deps, remote_deps)

if __name__ == "__main__":
    unittest.main(argv=[''])
