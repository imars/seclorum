# seclorum/agents/developer.py
from typing import Tuple, Any
from seclorum.agents.base import AbstractAggregate, AbstractAgent
from seclorum.models import Task, CodeOutput, TestResult, create_model_manager
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect
from seclorum.agents.debugger import Debugger


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
        debugger = Debugger("dev_task", self.session_id, self.model_manager)

        self.add_agent(architect)
        self.add_agent(generator, [(architect.name, {"status": "planned"})])
        self.add_agent(tester, [(generator.name, {"status": "generated"})])
        self.add_agent(executor, [(tester.name, {"status": "tested"})])
        self.add_agent(debugger, [(executor.name, {"status": "tested", "passed": False})])  # Debug on test failure

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
        if status == "tested" and isinstance(result, TestResult):
            if result.passed:
                self.log_update(f"Task {task.task_id} passed tests, workflow complete")
                return status, result  # Stop here if tests pass
            else:
                self.log_update(f"Test failed for Task {task.task_id}, triggering debug")
                debugger = self.agents.get("Debugger_dev_task")
                if debugger and task.task_id in self.tasks:
                    new_task = Task(
                        task_id=task.task_id,
                        description=task.description,
                        parameters=self.tasks[task.task_id]["outputs"]
                    )
                    debug_status, debug_result = debugger.process_task(new_task)
                    self._propagate(debugger.name, debug_status, debug_result, task)
                    status, result = debug_status, debug_result
        return status, result

    def process_task(self, task: Task) -> Tuple[str, Any]:
        """Process a task by orchestrating the agent workflow."""
        self.log_update(f"Developer processing Task {task.task_id}")
        return self.orchestrate(task)
