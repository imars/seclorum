# seclorum/agents/developer.py
from typing import Tuple, Any
from seclorum.agents.base import AbstractAggregate
from seclorum.models import Task, create_model_manager
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.architect import Architect
from seclorum.agents.debugger import Debugger
from typing import Any, Dict, List, Optional, Tuple, Set

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
        return super().orchestrate(task, stop_at)
