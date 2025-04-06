# seclorum/agents/outsourcing.py
import requests
from seclorum.agents.base import AbstractAgent
from seclorum.models import Task, OutsourcedTaskInput, OutsourcedTaskOutput
from seclorum.agents.memory_manager import MemoryManager

class Outsourcing(AbstractAgent):
    def __init__(self, task_id: str, session_id: str, api_endpoint: str, memory: MemoryManager = None):
        super().__init__(f"Outsourcing_{task_id}", session_id)
        self.task_id = task_id
        self.api_endpoint = api_endpoint
        self.memory = memory or MemoryManager(session_id)

    def process_task(self, task: Task) -> tuple[str, str]:
        self.logger.info(f"Outsourcing Task {task.task_id}")
        input_data = OutsourcedTaskInput(query=task.description, context=task.parameters.get("context"))
        self.memory.save(prompt=f"Task {task.task_id}: {input_data.query}", task_id=task.task_id)

        # Placeholder API call
        response = requests.post(self.api_endpoint, data=input_data.to_json())
        output = OutsourcedTaskOutput.from_json(response.text)

        result = f"Outsourced result: {output.result} (confidence: {output.confidence})"
        self.memory.save(response=result, task_id=task.task_id)  # Pass TestResult object
        return "outsourced", result
