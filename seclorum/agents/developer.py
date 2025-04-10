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

    # seclorum/agents/developer.py (merged orchestrate)
    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        status, result = super().orchestrate(task, stop_at)
        self.log_update(f"Orchestration completed with status: {status}")

        # Force progression if stopped early or to ensure complete workflow
        if status == "planned" and "Generator_dev_task" in self.agents:
            self.log_update("Forcing Generator to process after Architect")
            generator = self.agents["Generator_dev_task"]
            status, result = generator.process_task(task)
            self.log_update(f"Forced Generator, new status: {status}")

        if status == "generated" and task.parameters.get("generate_tests", False) and "Tester_dev_task" in self.agents:
            self.log_update("Forcing Tester to process after Generator")
            tester = self.agents["Tester_dev_task"]
            status, result = tester.process_task(task)
            self.log_update(f"Forced Tester, new status: {status}")

        if status == "tested" and "Executor_dev_task" in self.agents:
            self.log_update("Forcing Executor to process after Tester")
            executor = self.agents["Executor_dev_task"]
            status, result = executor.process_task(task)
            self.log_update(f"Forced Executor, new status: {status}")

        if status == "tested" and isinstance(result, TestResult) and not result.passed and "Debugger_dev_task" in self.agents:
            self.log_update("Forcing Debugger to process due to failed tests")
            debugger = self.agents["Debugger_dev_task"]
            status, result = debugger.process_task(task)
            self.log_update(f"Forced Debugger, new status: {status}")

        # Ensure the correct result is returned based on final status
        if status == "generated":
            result = task.parameters.get("Generator_dev_task", {}).get("result", result)
        elif status == "tested":
            result = task.parameters.get("Executor_dev_task", {}).get("result",
                     task.parameters.get("Tester_dev_task", {}).get("result", result))
        elif status == "debugged":
            result = task.parameters.get("Debugger_dev_task", {}).get("result",
                     task.parameters.get("Executor_dev_task", {}).get("result", result))

        self.log_update(f"Final result type: {type(result).__name__}, content: {result}")
        return status, result
