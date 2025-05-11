# seclorum/languages/__init__.py
from typing import List, Optional
from seclorum.models import Task
from seclorum.utils.logger import logger

class LanguageHandler:
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        raise NotImplementedError

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        raise NotImplementedError

    def get_test_prompt(self, code: str) -> Optional[str]:
        return None

    def get_fallback_code(self, task: Task) -> str:
        return ""

    def validate_code(self, code: str) -> bool:
        return bool(code.strip())

class JavaScriptHandler(LanguageHandler):
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        logger.debug(f"Mapping JavaScript output files: {generic_files}")
        mapping = {
            "main_output": "counter.js",
            "config_output": "settings.js",
            "test_output": "tests.js"
        }
        result = []
        for generic in generic_files:
            specific = mapping.get(generic, generic if generic.endswith(".js") else "counter.js")
            if specific not in result:
                result.append(specific)
        logger.debug(f"Mapped JavaScript files: {result}")
        return result

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating JavaScript prompt for task={task.task_id}, output_file={output_file}")
        if output_file in ["settings.js", "config_output"]:
            return (
                f"Task Description:\n{task.description}\n\n"
                f"Architect's Plan:\n{plan}\n\n"
                f"Generate JavaScript configuration code for {output_file}. "
                "Define configurable parameters (e.g., initial count, increment value) as a JavaScript object. "
                "Return clean JavaScript code, no comments, no markdown."
            )
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JavaScript code for {output_file} based on the task description. "
            "Implement a counter that increments when a button is clicked. "
            "Interact with HTML elements: button#increment, span#count. "
            "Return clean JavaScript code, no comments, no markdown."
        )

class HTMLHandler(LanguageHandler):
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        logger.debug(f"Mapping HTML output files: {generic_files}")
        mapping = {
            "main_output": "counter.html",
            "config_output": "index.html"
        }
        result = []
        for generic in generic_files:
            specific = mapping.get(generic, generic if generic.endswith(".html") else "counter.html")
            if specific not in result:
                result.append(specific)
        logger.debug(f"Mapped HTML files: {result}")
        return result

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating HTML prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate HTML code for {output_file} based on the task description. "
            "Include a button (id='increment') and a span (id='count') to display the counter value. "
            "Include <script src='counter.js'>. "
            "Return clean HTML code, no JavaScript, no comments, no markdown."
        )

class CSSHandler(LanguageHandler):
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        logger.debug(f"Mapping CSS output files: {generic_files}")
        mapping = {
            "main_output": "styles.css"
        }
        result = []
        for generic in generic_files:
            specific = mapping.get(generic, generic if generic.endswith(".css") else "styles.css")
            if specific not in result:
                result.append(specific)
        logger.debug(f"Mapped CSS files: {result}")
        return result

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating CSS prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate CSS code for {output_file} based on the task description. "
            "Style the counter button (id='increment') and count display (id='count'). "
            "Return clean CSS code, no comments, no markdown."
        )

class JSONHandler(LanguageHandler):
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        logger.debug(f"Mapping JSON output files: {generic_files}")
        mapping = {
            "main_output": "package.json",
            "config_output": "config.json"
        }
        result = []
        for generic in generic_files:
            specific = mapping.get(generic, generic if generic.endswith(".json") else "package.json")
            if specific not in result:
                result.append(specific)
        logger.debug(f"Mapped JSON files: {result}")
        return result

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating JSON prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate JSON code for {output_file} based on the task description. "
            "For package.json, include basic Node.js project metadata. "
            "Return clean JSON code, no comments, no markdown."
        )

class TextHandler(LanguageHandler):
    def map_output_files(self, generic_files: List[str], task: Task) -> List[str]:
        logger.debug(f"Mapping Text output files: {generic_files}")
        mapping = {
            "main_output": "README.md"
        }
        result = []
        for generic in generic_files:
            specific = mapping.get(generic, generic if generic.endswith(".md") else "README.md")
            if specific not in result:
                result.append(specific)
        logger.debug(f"Mapped Text files: {result}")
        return result

    def get_code_prompt(self, task: Task, output_file: str) -> str:
        plan = task.parameters.get(f"Architect_{task.task_id}", {}).get("result", "")
        logger.debug(f"Generating Text prompt for task={task.task_id}, output_file={output_file}")
        return (
            f"Task Description:\n{task.description}\n\n"
            f"Architect's Plan:\n{plan}\n\n"
            f"Generate documentation for {output_file} based on the task description. "
            "For README.md, include project overview and usage instructions. "
            "Return clean Markdown text, no comments, no markdown code blocks."
        )

LANGUAGE_HANDLERS = {
    "javascript": JavaScriptHandler(),
    "html": HTMLHandler(),
    "css": CSSHandler(),
    "json": JSONHandler(),
    "text": TextHandler()
}
