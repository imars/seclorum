# seclorum/agents/generator.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_HANDLERS
from typing import Tuple
import re
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        logger.debug(f"Generator initialized for Task {task_id}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        logger.debug(f"Generating code for task: {task.description[:100]}...")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")

        handler = LANGUAGE_HANDLERS.get(language)
        if not handler:
            logger.error(f"Unsupported language: {language}")
            return "failed", CodeOutput(code="", tests=None)

        code_prompt = handler.get_code_prompt(task, output_file)
        use_remote = task.parameters.get("use_remote", False)
        raw_code = self.infer(code_prompt, task, use_remote=use_remote, use_context=False, max_tokens=4000)
        code = re.sub(r'```(?:javascript|html|python|cpp|css)?\n|\n```|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?', '', raw_code).strip()

        if not handler.validate_code(code):
            logger.warning(f"Invalid {language} code generated for {output_file}")
            code = ""
        logger.debug(f"Generated code for {output_file}:\n{code[:200]}...")

        tests = None
        if task.parameters.get("generate_tests", False) and code:
            test_prompt = handler.get_test_prompt(code)
            raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False, max_tokens=2000)
            tests = re.sub(r'```(?:javascript|html|python|cpp)?\n|\n```|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid|mock|recommended)[^\n]*?\n?', '', raw_tests).strip()
            if not tests.startswith(("describe(", "test(")):
                tests = None
            logger.debug(f"Generated tests for {output_file}:\n{tests[:200]}...")

        result = CodeOutput(code=code, tests=tests)
        self.save_output(task, result, status="generated")
        self.commit_changes(f"Generated {language} code for {output_file}")
        return "generated", result

    def start(self):
        logger.debug("Starting generator")

    def stop(self):
        logger.debug("Stopping generator")
