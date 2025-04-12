# seclorum/agents/generator.py
from seclorum.agents.base import Agent
from seclorum.models import Task, CodeOutput, create_model_manager, ModelManager
from seclorum.languages import LANGUAGE_CONFIG
from typing import Tuple
import re

class Generator(Agent):
    def __init__(self, task_id: str, session_id: str, model_manager: ModelManager):
        super().__init__(f"Generator_{task_id}", session_id)
        self.task_id = task_id
        self.model = model_manager
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
        self.log_update(f"Generator initialized for Task {task_id} with model {self.model_manager.model_name}")

    def process_task(self, task: Task) -> Tuple[str, CodeOutput]:
        self.log_update(f"Generating code for task: {task.description}")
        language = task.parameters.get("language", "javascript").lower()
        output_file = task.parameters.get("output_file", "output")
        config = LANGUAGE_CONFIG.get(language, LANGUAGE_CONFIG["javascript"])

        # Include Architect's plan if available
        architect_key = next((k for k in task.parameters if k.startswith("Architect_")), None)
        plan = task.parameters.get(architect_key, {}).get("result", "") if architect_key else ""
        if isinstance(plan, str) and plan.strip():
            self.log_update(f"Using Architect plan:\n{plan}")
        else:
            plan = ""
            self.log_update("No valid Architect plan found")

        # Tailor prompt to language and output file
        code_prompt = (
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate {language} code for {output_file} based on the plan. "
            f"Focus on the parts relevant to {language} and the file's purpose (e.g., game logic for .js, UI for .html).\n"
        ) + (
            "Return only the raw, executable JavaScript code suitable for browser environments using the global THREE object from a CDN, "
            "avoiding Node.js require statements, without tags, markup, comments, or explanations."
            if language == "javascript" else
            "Return only the raw HTML content, including necessary UI elements, without comments or explanations."
            if language == "html" else
            config["code_prompt"].format(description=task.description)
        )

        use_remote = task.parameters.get("use_remote", False)
        raw_code = self.infer(code_prompt, task, use_remote=use_remote, use_context=False)
        code = re.sub(r'```(?:javascript|html|python|cpp|css)?\n|\n```|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid)[^\n]*?\n?', '', raw_code).strip()
        if not code or code.lower().startswith(("error", "invalid")):
            self.log_update("Invalid code generated, discarding")
            code = ""
        self.log_update(f"Raw generated code for {output_file}:\n{code}")

        tests = None
        if task.parameters.get("generate_tests", False) and config["test_prompt"] and code:
            test_prompt = config["test_prompt"].format(code=code) + (
                " Return only the raw, executable Jest test code for Node.js, compatible with Three.js browser code, "
                "without Markdown, comments, instructions, or explanations. Ensure tests reference the code via global variables "
                "(e.g., scene, camera, drone) and avoid require statements."
                if language == "javascript" else
                " Return only the raw HTML test code or validation script, without comments or explanations."
                if language == "html" else ""
            )
            raw_tests = self.infer(test_prompt, task, use_remote=use_remote, use_context=False)
            tests = re.sub(r'```(?:javascript|html|python|cpp)?\n|\n```|[^\x00-\x7F]+|[^\n]*?(error|warning|invalid|mock|recommended)[^\n]*?\n?', '', raw_tests).strip()
            if language == "javascript" and not tests.startswith(("describe(", "test(")):
                tests = None
            self.log_update(f"Generated tests for {output_file}:\n{tests}")

        result = CodeOutput(code=code, tests=tests)
        self.save_output(task, result, status="generated")
        self.commit_changes(f"Generated {language} code for {output_file} for {task.task_id}")
        return "generated", result

    def start(self):
        self.log_update("Starting generator")

    def stop(self):
        self.log_update("Stopping generator")
