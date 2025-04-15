from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
from typing import Tuple
import re
import logging
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Generator initialized for Task {task_id}, session_id={session_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        logger.debug(f"Generating code for task={task.task_id}, description={task.description[:100]}, "
                     f"parameters={task.parameters}")
        start_time = time.time()
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")

        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            result = CodeOutput(code="", tests=None)
            self.track_flow(task, "failed", result, task.parameters.get("use_remote", False))
            return "failed", result

        try:
            code = handler.get_code(task, output_file)
            if not code:
                code_prompt = handler.get_code_prompt(task, output_file)
                logger.debug(f"Code prompt: {code_prompt[:200]}...")
                use_remote = task.parameters.get("use_remote", False)
                raw_code = self.infer(code_prompt, task, use_remote=use_remote, use_context=False, max_tokens=4000)
                logger.debug(f"Raw inferred code for {output_file}: {raw_code[:200]}...")
                code = re.sub(r'```(?:javascript|html|python|cpp|css)?\n|\n```|[^\x00-\x7F]+', '', raw_code).strip()

            logger.debug(f"Generated code before validation: {code[:200]}...")
            if not handler.validate_code(code):
                logger.warning(f"Invalid {language} code generated for {output_file}, falling back to default")
                code = handler.get_fallback_code(task)
                if not handler.validate_code(code):
                    logger.error(f"Fallback {language} code invalid for {output_file}")
                    code = ""

            logger.debug(f"Final generated code for {output_file}: {code[:200]}...")

            tests = None
            if task.parameters.get("generate_tests", False) and code and language == "javascript":
                test_prompt = handler.get_test_prompt(code)
                logger.debug(f"Test prompt: {test_prompt[:200]}...")
                use_remote = task.parameters.get("use_remote", False)
                raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False, max_tokens=2000)
                logger.debug(f"Raw inferred tests for {output_file}: {raw_tests[:200]}...")
                tests = re.sub(r'```(?:javascript|html|python|cpp)?\n|\n```|[^\x00-\x7F]+', '', raw_tests).strip()
                if not tests.startswith(("describe(", "test(")):
                    logger.warning(f"Invalid Jest tests for {output_file}, discarding")
                    tests = None
                logger.debug(f"Generated tests for {output_file}: {tests[:200]}..." if tests else "No valid tests generated")

            result = CodeOutput(code=code, tests=tests)
            self.save_output(task, result, status="generated")
            self.commit_changes(f"Generated {language} code for {output_file}")
            logger.debug(f"Tracking flow for {self.name}: status=generated, task_id={task.task_id}")
            self.track_flow(task, "generated", result, task.parameters.get("use_remote", False))
            elapsed = time.time() - start_time
            logger.debug(f"Generator.process_task completed in {elapsed:.2f}s")
            return "generated", result
        except Exception as e:
            logger.error(f"Generation failed for {output_file}: {str(e)}")
            result = CodeOutput(code="", tests=None)
            self.track_flow(task, "failed", result, task.parameters.get("use_remote", False))
            elapsed = time.time() - start_time
            logger.debug(f"Generator.process_task failed in {elapsed:.2f}s")
            return "failed", result
