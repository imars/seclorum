# seclorum/agents/developer.py
from typing import Tuple, Any
from seclorum.agents.base import AbstractAggregate, AbstractAgent
from seclorum.models import Task, CodeOutput, TestResult, create_model_manager
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect

class Developer(AbstractAggregate):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id)
        self.name = "Developer"
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="codellama")
        self.setup_workflow()

    def setup_workflow(self):
        architect = Architect("dev_task", self.session_id, self.model_manager)
        generator = Generator("dev_task", self.session_id, self.model_manager)
        tester = Tester("dev_task", self.session_id, self.model_manager)
        executor = Executor("dev_task", self.session_id)

        self.add_agent(architect)
        self.add_agent(generator, [(architect.name, {"status": "planned"})])
        self.add_agent(tester, [(generator.name, {"status": "generated"})])
        self.add_agent(executor, [(tester.name, {"status": "tested"})])

    def debug(self, task: Task, test_result: TestResult) -> Tuple[str, CodeOutput]:
        if not test_result.passed and test_result.output:
            self.log_update(f"Debugging Task {task.task_id}: {test_result.output}")
            debug_prompt = f"Fix this Python code that failed with error:\n{test_result.output}\n\nCode:\n{test_result.test_code}"
            fixed_code_str = self.model_manager.generate(debug_prompt)
            fixed_code = CodeOutput(code=fixed_code_str)
            self.memory.save(response=fixed_code, task_id=task.task_id)
            return "debugged", fixed_code
        return "tested", CodeOutput(code=test_result.test_code)

    def orchestrate(self, task: Task) -> Tuple[str, Any]:
        status, result = super().orchestrate(task)
        if status == "tested" and isinstance(result, TestResult) and not result.passed:
            return self.debug(task, result)
        return status, result
