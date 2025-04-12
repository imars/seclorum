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
        self.model_manager = model_manager or create_model_manager(provider="ollama", model_name="llama3.2:latest")
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
        self.log_update(f"Starting orchestration for task {task.task_id}, stop_at={stop_at}")
        self.log_update(f"Initial task parameters: {task.parameters}")

        # Dynamically find agent keys
        generator_key = next((k for k in self.agents if k.startswith("Generator_")), None)
        tester_key = next((k for k in self.agents if k.startswith("Tester_")), None)
        executor_key = next((k for k in self.agents if k.startswith("Executor_")), None)
        debugger_key = next((k for k in self.agents if k.startswith("Debugger_")), None)

        self.log_update(f"Available agent keys: generator={generator_key}, tester={tester_key}, executor={executor_key}, debugger={debugger_key}")

        # Ensure Architect runs
        architect_key = next((k for k in self.agents if k.startswith("Architect_")), None)
        if architect_key and architect_key not in task.parameters:
            self.log_update(f"{architect_key} output missing, forcing execution")
            architect = self.agents[architect_key]
            status, result = architect.process_task(task)
            self.log_update(f"Forced {architect_key}, status: {status}, result: {result}")

        # Ensure Generator runs
        if generator_key and generator_key not in task.parameters:
            self.log_update(f"{generator_key} output missing, forcing execution")
            generator = self.agents[generator_key]
            status, result = generator.process_task(task)
            self.log_update(f"Forced {generator_key}, status: {status}, result: {result}")
        else:
            status = "generated" if generator_key in task.parameters else "planned"
            result = task.parameters.get(generator_key, {}).get("result") if generator_key else None
            self.log_update(f"{generator_key} output already present: {result}")

        # Run Tester if generate_tests is True
        if task.parameters.get("generate_tests", False) and tester_key:
            self.log_update(f"Forcing {tester_key} to process")
            tester = self.agents[tester_key]
            status, result = tester.process_task(task)
            self.log_update(f"Forced {tester_key}, status: {status}, result: {result}")

        # Run Executor if execute is True or tests exist
        if (task.parameters.get("execute", False) or tester_key in task.parameters) and executor_key:
            self.log_update(f"Forcing {executor_key} to process")
            executor = self.agents[executor_key]
            status, result = executor.process_task(task)
            self.log_update(f"Forced {executor_key}, status: {status}, result: {result}")

        # Run Debugger if execution failed
        if status == "tested" and isinstance(result, TestResult) and not result.passed and debugger_key:
            self.log_update(f"Forcing {debugger_key} due to failed execution")
            debugger = self.agents[debugger_key]
            status, result = debugger.process_task(task)
            self.log_update(f"Forced {debugger_key}, status: {status}, result: {result}")

        # Finalize output
        final_result = task.parameters.get(generator_key, {}).get("result") if generator_key in task.parameters else result
        self.log_update(f"Checking {generator_key} output: {final_result}")
        if not isinstance(final_result, CodeOutput) or not final_result.code.strip():
            self.log_update(f"Warning: Invalid or empty Generator output: {final_result}")

        status = "tested" if (task.parameters.get("generate_tests", False) or task.parameters.get("execute", False)) else "generated"
        self.log_update(f"Final result type: {type(final_result).__name__}, content: {final_result}")
        return status, final_result
