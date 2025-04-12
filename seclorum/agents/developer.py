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
        architect_key = next((k for k in self.agents if k.startswith("Architect_")), None)
        generator_key = next((k for k in self.agents if k.startswith("Generator_")), None)
        tester_key = next((k for k in self.agents if k.startswith("Tester_")), None)
        executor_key = next((k for k in self.agents if k.startswith("Executor_")), None)
        debugger_key = next((k for k in self.agents if k.startswith("Debugger_")), None)

        self.log_update(f"Available agent keys: architect={architect_key}, generator={generator_key}, tester={tester_key}, executor={executor_key}, debugger={debugger_key}")

        # Run Architect
        if architect_key:
            try:
                architect = self.agents[architect_key]
                status, result = architect.process_task(task)
                self.log_update(f"{architect_key} executed, status: {status}, result: {result}")
                task.parameters[architect_key] = {"status": status, "result": result}
            except Exception as e:
                self.log_update(f"{architect_key} failed: {str(e)}")
                task.parameters[architect_key] = {"status": "failed", "result": ""}

        # Run Generator
        if generator_key:
            try:
                generator = self.agents[generator_key]
                status, result = generator.process_task(task)
                self.log_update(f"{generator_key} executed, status: {status}, result: {result}")
                task.parameters[generator_key] = {"status": status, "result": result}
            except Exception as e:
                self.log_update(f"{generator_key} failed: {str(e)}")
                task.parameters[generator_key] = {"status": "failed", "result": CodeOutput(code="", tests=None)}

        # Run Tester if generate_tests is True
        final_status = "generated"
        final_result = task.parameters.get(generator_key, {}).get("result") if generator_key else None
        if task.parameters.get("generate_tests", False) and tester_key:
            try:
                tester = self.agents[tester_key]
                status, result = tester.process_task(task)
                self.log_update(f"{tester_key} executed, status: {status}, result: {result}")
                task.parameters[tester_key] = {"status": status, "result": result}
                final_status = "tested"
                final_result = result
            except Exception as e:
                self.log_update(f"{tester_key} failed: {str(e)}")
                task.parameters[tester_key] = {"status": "failed", "result": TestResult(test_code="", passed=False, output=str(e))}

        # Run Executor if execute is True or Tester ran
        if (task.parameters.get("execute", False) or tester_key in task.parameters) and executor_key:
            try:
                executor = self.agents[executor_key]
                status, result = executor.process_task(task)
                self.log_update(f"{executor_key} executed, status: {status}, result: {result}")
                task.parameters[executor_key] = {"status": status, "result": result}
                final_status = "tested"
                final_result = result
            except Exception as e:
                self.log_update(f"{executor_key} failed: {str(e)}")
                task.parameters[executor_key] = {"status": "failed", "result": TestResult(test_code="", passed=False, output=str(e))}

        # Run Debugger if tests failed
        if final_status == "tested" and isinstance(final_result, TestResult) and not final_result.passed and debugger_key:
            try:
                debugger = self.agents[debugger_key]
                status, result = debugger.process_task(task)
                self.log_update(f"{debugger_key} executed, status: {status}, result: {result}")
                task.parameters[debugger_key] = {"status": status, "result": result}
                final_status = "debugged"
                final_result = result
            except Exception as e:
                self.log_update(f"{debugger_key} failed: {str(e)}")
                task.parameters[debugger_key] = {"status": "failed", "result": CodeOutput(code="", tests=None)}

        # Select final code output
        if final_status == "debugged" and debugger_key in task.parameters:
            final_result = task.parameters[debugger_key].get("result")
            self.log_update("Selected Debugger output as final result")
        elif generator_key in task.parameters:
            final_result = task.parameters[generator_key].get("result")
            self.log_update("Selected Generator output as final result")
        else:
            self.log_update("Warning: No valid output from any agent")
            final_status = "failed"
            final_result = CodeOutput(code="", tests=None)

        # Validate final output
        if not isinstance(final_result, CodeOutput) or not final_result.code.strip():
            self.log_update(f"Invalid final output: {final_result}")
            final_status = "failed"
            final_result = CodeOutput(code="", tests=None)

        self.log_update(f"Final result type: {type(final_result).__name__}, content: {final_result}")
        return final_status, final_result
