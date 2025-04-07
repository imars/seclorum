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
        self.add_agent(debugger, [(executor.name, {"status": "tested", "passed": False})])

    def process_task(self, task: Task) -> Tuple[str, Any]:
        self.log_update(f"Developer processing Task {task.task_id}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task) -> Tuple[str, Any]:
        status, result = super().orchestrate(task)
        task_id = task.task_id
        # Check the latest task state
        if task_id in self.tasks:
            latest_status = self.tasks[task_id]["status"]
            latest_result = self.tasks[task_id]["result"]
            if latest_status == "tested" and isinstance(latest_result, TestResult):
                if latest_result.passed:
                    self.log_update(f"Task {task_id} passed tests, workflow complete")
                    return "tested", latest_result  # Return passing result immediately
                else:
                    self.log_update(f"Test failed for Task {task_id}, triggering debug")
                    debugger = self.agents.get("Debugger_dev_task")
                    if debugger:
                        new_task = Task(
                            task_id=task_id,
                            description=task.description,
                            parameters=self.tasks[task_id]["outputs"]
                        )
                        debug_status, debug_result = debugger.process_task(new_task)
                        self._propagate(debugger.name, debug_status, debug_result, task)
                        return debug_status, debug_result
        return status, result
