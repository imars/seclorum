# seclorum/agents/tester.py
import logging
from typing import Tuple, Any, Optional
from seclorum.agents.agent import Agent
from seclorum.models import CodeOutput, TestResult
from seclorum.languages import validate_code, generate_test_code

logger = logging.getLogger(__name__)

class Tester(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager=None):
        super().__init__(task_id, session_id, model_manager)
        self.name = f"Tester_{task_id}"
        logger.debug(f"Tester initialized for Task {task_id}, session_id={session_id}")

    def process_task(self, task: Any, **kwargs) -> Tuple[str, Any]:
        logger.debug(f"Testing code for task={task.task_id}, description={task.description[:50]}...")
        logger.debug(f"Task parameters: {task.parameters}")

        try:
            # Extract generated code from parameters
            generator_output = None
            for key, value in task.parameters.items():
                if isinstance(value, dict) and value.get("status") == "generated":
                    generator_output = value.get("result")
                    break

            if not generator_output or not isinstance(generator_output, CodeOutput) or not generator_output.code:
                logger.error("No valid generated code found in task parameters")
                return "failed", None

            code = generator_output.code
            language = task.parameters.get("language", "javascript")
            output_file = task.parameters.get("output_file", "output.js")

            # Validate generated code
            is_valid, validation_error = validate_code(code, language)
            if not is_valid:
                logger.error(f"Code validation failed: {validation_error}")
                return "failed", CodeOutput(code=code, tests=None, error=validation_error)

            # Generate tests if requested
            if task.parameters.get("generate_tests", False):
                try:
                    test_code = generate_test_code(code, language, task.description)
                    logger.debug(f"Generated test code for {output_file}: {test_code[:100]}...")
                except Exception as e:
                    logger.error(f"Test generation failed: {str(e)}")
                    return "failed", CodeOutput(code=code, tests=None, error=str(e))
            else:
                test_code = None

            # Simulate test execution (mock for now)
            test_result = TestResult(passed=True, output="Tests passed (mock)")
            logger.debug(f"Test result: passed={test_result.passed}, output={test_result.output}")

            return "tested", CodeOutput(code=code, tests=test_code, test_result=test_result)

        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {str(e)}")
            return "failed", None
