# seclorum/agents/developer.py
from typing import Tuple, Any
from seclorum.agents.base import Aggregate
from seclorum.models import Task, create_model_manager, CodeOutput, TestResult
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect
from seclorum.agents.debugger import Debugger
from typing import Optional

class Developer(Aggregate):
    def __init__(self, session_id: str, model_manager=None):
        super().__init__(session_id, model_manager)
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
        self.add_agent(generator, [("Architect_dev_task", {"status": "planned"})])
        self.add_agent(tester, [("Generator_dev_task", {"status": "generated"})])
        self.add_agent(executor, [
            ("Tester_dev_task", {"status": "tested"}),
            ("Generator_dev_task", {"status": "generated"})
        ])
        self.add_agent(debugger, [("Executor_dev_task", {"status": "tested", "passed": False})])

    def process_task(self, task: Task) -> Tuple[str, Any]:
        self.log_update(f"Developer processing Task {task.task_id}")
        return self.orchestrate(task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        status, result = super().orchestrate(task, stop_at)
        self.log_update(f"Orchestration completed with status: {status}")

        # Force progression if stopped early
        if status == "planned":
            generator = self.agents["Generator_dev_task"]
            status, result = generator.process_task(task)
            self.log_update(f"Forced Generator, new status: {status}")

        if status == "generated" and task.parameters.get("generate_tests", False):
            tester = self.agents["Tester_dev_task"]
            status, result = tester.process_task(task)
            self.log_update(f"Forced Tester, new status: {status}")

        if status == "tested":
            executor = self.agents["Executor_dev_task"]
            status, result = executor.process_task(task)
            self.log_update(f"Forced Executor, new status: {status}")

        if status == "tested" and not result.passed:
            debugger = self.agents["Debugger_dev_task"]
            status, result = debugger.process_task(task)
            self.log_update(f"Forced Debugger, new status: {status}")

        return status, result
