# tests/test_architect.py
import unittest
import logging
import json
import re
from typing import Optional
from seclorum.models import Task, Plan, TaskFactory
from seclorum.agents.architect import Architect
from seclorum.models import create_model_manager  # Updated import

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

class TestArchitect(unittest.TestCase):
    def setUp(self):
        """Set up the test environment with Google, Ollama, and Guidance model managers."""
        self.session_id = "test_session"
        self.google_model_manager = create_model_manager(provider="google_ai_studio", model_name="gemini-1.5-flash")
        self.ollama_model_manager = None
        self.guidance_model_manager = None

        # Try Guidance first, then fall back to llama_cpp, then Ollama
        try:
            self.guidance_model_manager = create_model_manager(provider="guidance", model_name="llama3.2:latest")
            logger.info("Initialized guidance model manager")
        except Exception as e:
            logger.error(f"Failed to initialize guidance model manager: {str(e)}")
            try:
                self.ollama_model_manager = create_model_manager(provider="llama_cpp", model_name="llama3.2:latest")
                logger.info("Initialized llama_cpp model manager")
            except Exception as e:
                logger.error(f"Failed to initialize llama_cpp model manager: {str(e)}. Falling back to Ollama.")
                self.ollama_model_manager = create_model_manager(provider="ollama", model_name="llama3.2:latest")

        self.google_architect = Architect(name="TestArchitectGoogle", session_id=self.session_id, model_manager=self.google_model_manager)
        if self.guidance_model_manager:
            self.local_architect = Architect(name="TestArchitectGuidance", session_id=self.session_id, model_manager=self.guidance_model_manager)
            logger.info("Using guidance provider for local architect")
        else:
            self.local_architect = Architect(name="TestArchitectOllama", session_id=self.session_id, model_manager=self.ollama_model_manager)
            logger.info("Using %s provider for local architect", self.ollama_model_manager.provider)

        logger.info("TestArchitect set up with session_id=%s", self.session_id)

    def validate_plan(self, status, result, raw_plan, task, expected_provider):
        """Common validation logic for plan output."""
        self.assertEqual(status, "generated", f"Expected status 'generated', got '{status}'")
        self.assertIsInstance(result, Plan, f"Expected Plan object, got {type(result).__name__}")

        # Validate plan structure
        self.assertTrue(hasattr(result, "subtasks"), "Plan must have 'subtasks' attribute")
        self.assertIsInstance(result.subtasks, list, "Subtasks must be a list")
        self.assertGreaterEqual(len(result.subtasks), 5, "Plan must include at least 5 subtasks for modularity")
        self.assertLessEqual(len(result.subtasks), 10, "Plan must include at most 10 subtasks to avoid over-segmentation")
        logger.info("Subtask count: %d", len(result.subtasks))

        # Check for specified output files
        output_files = [f for subtask in result.subtasks for f in subtask.parameters.get("output_files", [])]
        required_files = task.parameters.get("output_files", [])
        for required_file in required_files:
            self.assertIn(required_file, output_files, f"Plan must include '{required_file}' output file")

        # Check for configuration file (settings.js for JavaScript)
        self.assertTrue(any("settings.js" in subtask.parameters.get("output_files", []) for subtask in result.subtasks),
                        "Plan must include a settings.js file (mapped from config_output)")

        # Validate subtask descriptions, parameters, dependencies, and prompts
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
            self.assertTrue(language, "Subtask must specify a language in parameters")
            self.assertNotEqual(language, "none", "Subtask language must not be 'none'")
            languages.add(language)
            if language == "css":
                self.assertTrue(all(f.endswith(".css") for f in output_files),
                               f"CSS subtask must output to .css files, got {output_files}")
            for dep_id in subtask.dependencies:
                self.assertIn(dep_id, task_ids, f"Dependency {dep_id} must be a valid subtask task_id")
            self.assertTrue(subtask.prompt, f"Subtask must have a non-empty prompt, got {subtask.prompt}")

        self.assertTrue(has_multiple_files, "At least one subtask must have multiple output files")
        self.assertGreaterEqual(len(languages), 3, "Plan must include at least 3 pipelines (e.g., HTML, CSS, JavaScript)")
        self.assertIn("html", languages, "Plan must include an HTML pipeline")
        self.assertIn("css", languages, "Plan must include a CSS pipeline")
        self.assertIn("javascript", languages, "Plan must include a JavaScript pipeline")

        # Validate dependencies
        html_task_ids = {s.task_id for s in result.subtasks if s.parameters.get("language").lower() == "html"}
        js_task_ids = {s.task_id for s in result.subtasks if s.parameters.get("language").lower() == "javascript"}
        for subtask in result.subtasks:
            language = subtask.parameters.get("language").lower()
            if language in ["javascript", "css"] and html_task_ids:
                self.assertTrue(any(dep_id in html_task_ids for dep_id in subtask.dependencies),
                               f"{language} subtask must depend on HTML")
            if language == "text" and js_task_ids:
                self.assertTrue(any(dep_id in js_task_ids for dep_id in subtask.dependencies),
                               "Text subtask must depend on JavaScript")

        # Validate retries (expect fewer with Guidance)
        history = self.local_architect.memory.load_conversation_history(task.task_id, f"TestArchitect{expected_provider.capitalize()}")
        retry_count = sum(1 for entry in history if "Inference attempt" in str(entry))
        logger.info("Retry count: %d", retry_count)
        if expected_provider == "guidance":
            self.assertLessEqual(retry_count, 1, "Guidance should require at most 1 retry")

        # Serialize plan for logging
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

        # Print raw plan output
        print("\n=== Raw Plan Output ===")
        try:
            parsed_plan = json.loads(raw_plan)
            print(json.dumps(parsed_plan, indent=2))
        except json.JSONDecodeError:
            logger.warning("Raw plan is not valid JSON, attempting to load from Memory")
            if history:
                _, stored_response, _ = history[-1]
                try:
                    stored_plan = json.loads(stored_response)
                    print(json.dumps(stored_plan, indent=2))
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse stored plan from Memory: {str(e)}")
                    print(raw_plan)
            else:
                logger.warning("No stored plan found in Memory")
                print(raw_plan)
        print("======================")

    def create_task(self, task_id: str, use_remote: bool, max_tokens: Optional[int] = None) -> Task:
        """Create a task for testing."""
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

    def test_guidance_availability(self):
        """Test that the guidance provider is available."""
        try:
            import guidance
            from guidance.models import LlamaCpp
            logger.info("Guidance and LlamaCpp imported successfully")
            self.assertTrue(self.guidance_model_manager is not None, "Guidance model manager should be initialized")
            self.assertEqual(self.local_architect.model.provider, "guidance",
                             f"Expected guidance model, got {self.local_architect.model.provider}")
        except ImportError as e:
            logger.warning(f"Guidance not available: {str(e)}. Test will use fallback provider.")
            self.assertTrue(self.ollama_model_manager is not None, "Fallback model manager should be initialized")
            self.assertIn(self.local_architect.model.provider, ["llama_cpp", "ollama"],
                          f"Expected fallback provider (llama_cpp or ollama), got {self.local_architect.model.provider}")

    def test_drone_racing_game_plan_local(self):
        """Test Architect produces a plan with dependencies, multiple output files, a settings file, and prompts using local model."""
        if self.guidance_model_manager:
            expected_provider = "guidance"
        elif self.ollama_model_manager and self.ollama_model_manager.provider == "llama_cpp":
            expected_provider = "llama_cpp"
        else:
            self.skipTest("Neither guidance nor llama_cpp model manager available; skipping test")
            return

        task = self.create_task("drone_racing_task_local", use_remote=False, max_tokens=4096)
        logger.info("Created task: task_id=%s, description=%s, use_remote=%s, max_tokens=%s",
                    task.task_id, task.description[:100], task.parameters.get("use_remote"), task.parameters.get("max_tokens"))

        # Process the task with local model
        status, result, raw_plan = self.local_architect.process_task(task)
        logger.info("Task processed: status=%s, result_type=%s", status, type(result).__name__)

        # Validate the plan
        self.validate_plan(status, result, raw_plan, task, expected_provider=expected_provider)

    def test_drone_racing_game_plan(self):
        """Test Architect produces a plan with dependencies, multiple output files, a settings file, and prompts using Google AI Studio."""
        task = self.create_task("drone_racing_task_google", use_remote=True, max_tokens=8192)
        logger.info("Created task: task_id=%s, description=%s, use_remote=%s, max_tokens=%s",
                    task.task_id, task.description[:100], task.parameters.get("use_remote"), task.parameters.get("max_tokens"))

        # Verify model
        self.assertEqual(self.google_architect.model.provider, "google_ai_studio",
                         f"Expected Google AI Studio model, got {self.google_architect.model.provider}")

        # Process the task with Google model
        status, result, raw_plan = self.google_architect.process_task(task)
        logger.info("Task processed: status=%s, result_type=%s", status, type(result).__name__)

        # Validate the plan
        self.validate_plan(status, result, raw_plan, task, expected_provider="google_ai_studio")

    def test_compare_local_and_remote_plans(self):
        """Test that local and remote plans are stored in Memory and compare their structure."""
        # Create tasks
        local_task = self.create_task("drone_racing_task_local", use_remote=False, max_tokens=4096)
        remote_task = self.create_task("drone_racing_task_google", use_remote=True, max_tokens=8192)

        # Process local plan
        local_status, local_result, local_raw_plan = self.local_architect.process_task(local_task)
        self.assertEqual(local_status, "generated", "Local plan generation failed")
        logger.info("Local plan processed: task_id=%s, subtask_count=%d",
                    local_task.task_id, len(local_result.subtasks))

        # Process remote plan
        remote_status, remote_result, remote_raw_plan = self.google_architect.process_task(remote_task)
        self.assertEqual(remote_status, "generated", "Remote plan generation failed")
        logger.info("Remote plan processed: task_id=%s, subtask_count=%d",
                    remote_task.task_id, len(remote_result.subtasks))

        # Load plans from Memory
        local_history = self.local_architect.memory.load_conversation_history(local_task.task_id, f"TestArchitect{self.local_architect.model.provider.capitalize()}")
        remote_history = self.google_architect.memory.load_conversation_history(remote_task.task_id, "TestArchitectGoogle")
        self.assertTrue(local_history, "Local plan not found in Memory")
        self.assertTrue(remote_history, "Remote plan not found in Memory")

        # Log raw responses for debugging
        local_prompt, local_response, _ = local_history[-1]
        remote_prompt, remote_response, _ = remote_history[-1]
        logger.debug("Local response: %s", local_response[:200])
        logger.debug("Remote response: %s", remote_response[:200])

        # Fix single-quoted JSON strings
        def fix_json(response):
            try:
                response = re.sub(r"'([^']*)'", r'"\1"', response)
                return json.loads(response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON after fixing quotes: {str(e)}")
                raise

        # Parse the latest plan responses
        try:
            local_plan = fix_json(local_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse local plan: {str(e)}")
            self.fail(f"Failed to parse local plan from Memory: {str(e)}")
        try:
            remote_plan = fix_json(remote_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse remote plan: {str(e)}")
            self.fail(f"Failed to parse remote plan from Memory: {str(e)}")

        # Compare plan structures
        local_subtasks = local_plan.get("subtasks", [])
        remote_subtasks = remote_plan.get("subtasks", [])
        self.assertGreaterEqual(len(local_subtasks), 5, "Local plan has too few subtasks")
        self.assertGreaterEqual(len(remote_subtasks), 5, "Remote plan has too few subtasks")
        self.assertLessEqual(len(local_subtasks), 10, "Local plan has too many subtasks")
        self.assertLessEqual(len(remote_subtasks), 10, "Remote plan has too many subtasks")
        logger.info("Local plan subtasks: %d, Remote plan subtasks: %d",
                    len(local_subtasks), len(remote_subtasks))

        # Compare output files
        local_files = set(f for s in local_subtasks for f in s.get("parameters", {}).get("output_files", []))
        remote_files = set(f for s in remote_subtasks for f in s.get("parameters", {}).get("output_files", []))
        common_files = local_files.intersection(remote_files)
        self.assertTrue(common_files, "No common output files between local and remote plans")
        logger.info("Common output files: %s", common_files)

        # Compare languages
        local_languages = set(s.get("language", "").lower() for s in local_subtasks)
        remote_languages = set(s.get("language", "").lower() for s in remote_subtasks)
        common_languages = local_languages.intersection(remote_languages)
        self.assertTrue(common_languages, "No common languages between local and remote plans")
        self.assertIn("html", common_languages, "HTML missing in common languages")
        self.assertIn("css", common_languages, "CSS missing in common languages")
        self.assertIn("javascript", common_languages, "JavaScript missing in common languages")
        logger.info("Common languages: %s", common_languages)

        # Compare dependencies
        local_deps = sum(len(s.get("dependencies", [])) for s in local_subtasks)
        remote_deps = sum(len(s.get("dependencies", [])) for s in remote_subtasks)
        self.assertGreater(local_deps, 0, "Local plan has no dependencies")
        self.assertGreater(remote_deps, 0, "Remote plan has no dependencies")
        logger.info("Local plan dependencies: %d, Remote plan dependencies: %d", local_deps, remote_deps)

        # Compare prompts
        local_prompts = set(s.get("prompt", "") for s in local_subtasks)
        remote_prompts = set(s.get("prompt", "") for s in remote_subtasks)
        common_prompts = local_prompts.intersection(remote_prompts)
        self.assertTrue(common_prompts, "No common prompts between local and remote plans")
        logger.info("Common prompts: %s", list(common_prompts)[:3])

        # Print plans for inspection
        print("\n=== Local Plan ===")
        print(json.dumps(local_plan, indent=2))
        print("==================")
        print("\n=== Remote Plan ===")
        print(json.dumps(remote_plan, indent=2))
        print("===================")

    def tearDown(self):
        """Clean up after tests."""
        self.google_architect.stop()
        self.local_architect.stop()
        logger.info("TestArchitect stopped")

if __name__ == "__main__":
    unittest.main()
