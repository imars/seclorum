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

    def process_task(self, Task: Task) -> Tuple[str, Any]:
        self.log_update(f"Developer processing Task {Task.task_id}")
        # No need to override infer; task.parameters["use_remote"] will propagate naturally
        return self.orchestrate(Task)

    def orchestrate(self, task: Task, stop_at: Optional[str] = None) -> Tuple[str, Any]:
        self.log_update(f"Starting orchestration for task {task.task_id}, stop_at={stop_at}")
        self.log_update(f"Initial task parameters: {task.parameters}")

        status, result = super().orchestrate(task, stop_at)
        self.log_update(f"Orchestration from superclass completed with status: {status}, result: {result}")
        self.log_update(f"Task parameters after superclass: {task.parameters}")

        # Dynamically find agent keys
        generator_key = next((k for k in self.agents if k.startswith("Generator_")), None)
        tester_key = next((k for k in self.agents if k.startswith("Tester_")), None)
        executor_key = next((k for k in self.agents if k.startswith("Executor_")), None)
        debugger_key = next((k for k in self.agents if k.startswith("Debugger_")), None)

        self.log_update(f"Available agent keys: generator={generator_key}, tester={tester_key}, executor={executor_key}, debugger={debugger_key}")

        # Ensure Generator runs if not already generated
        if status in ["planned", "initial"] and generator_key and generator_key not in task.parameters:
            self.log_update(f"Forcing {generator_key} to process due to missing output")
            generator = self.agents[generator_key]
            status, result = generator.process_task(task)
            self.log_update(f"Forced {generator_key}, new status: {status}, result: {result}")
            self.log_update(f"Post-Generator task parameters: {task.parameters}")

        # Proceed with testing if requested
        if status == "generated" and task.parameters.get("generate_tests", False) and tester_key:
            self.log_update(f"Forcing {tester_key} to process after generation")
            tester = self.agents[tester_key]
            status, result = tester.process_task(task)
            self.log_update(f"Forced {tester_key}, new status: {status}, result: {result}")
            self.log_update(f"Post-Tester task parameters: {task.parameters}")
        elif status == "generated" and not task.parameters.get("generate_tests", False):
            result = task.parameters.get(generator_key, {}).get("result", result) if generator_key else result
            self.log_update("No tests requested, stopping at generation")
            if not isinstance(result, CodeOutput) or not result.code.strip():
                self.log_update(f"Warning: Invalid or empty Generator output: {result}")
            return status, result

        # Execute if tested
        if status == "tested" and executor_key:
            self.log_update(f"Forcing {executor_key} to process after testing")
            executor = self.agents[executor_key]
            status, result = executor.process_task(task)
            self.log_update(f"Forced {executor_key}, new status: {status}, result: {result}")
            self.log_update(f"Post-Executor task parameters: {task.parameters}")

        # Debug if tests failed
        if status == "tested" and isinstance(result, TestResult) and not result.passed and debugger_key:
            self.log_update(f"Forcing {debugger_key} to process due to failed tests")
            debugger = self.agents[debugger_key]
            status, result = debugger.process_task(task)
            self.log_update(f"Forced {debugger_key}, new status: {status}, result: {result}")
            self.log_update(f"Post-Debugger task parameters: {task.parameters}")

        # Fallback to Generator's output if available and valid
        final_result = result
        if generator_key:
            generator_result = task.parameters.get(generator_key, {}).get("result")
            self.log_update(f"Checking {generator_key} output: {generator_result}")
            if isinstance(generator_result, CodeOutput) and generator_result.code.strip():
                final_result = generator_result
                status = "generated" if status in ["tested", "debugged"] else status
                self.log_update(f"Preserving {generator_key} output as final result: {final_result}")
            elif generator_key not in task.parameters:
                self.log_update(f"No {generator_key} output found in task parameters")
            else:
                self.log_update(f"Invalid {generator_key} output: {generator_result}")

        # Adjust status based on result type
        if isinstance(final_result, CodeOutput):
            status = "generated" if status not in ["planned", "generated"] else status
        elif isinstance(final_result, TestResult):
            status = "tested" if status not in ["tested", "debugged"] else status

        self.log_update(f"Final result type: {type(final_result).__name__}, content: {final_result}")
        return status, final_result
