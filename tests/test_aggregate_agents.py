# tests/test_aggregate_agents.py
import unittest
from seclorum.models import Task
from seclorum.agents.developer import Developer
from seclorum.models.manager import MockModelManager

class TestAggregateAgents(unittest.TestCase):
    def setUp(self):
        self.session_id = "test_session_agg"
        self.task_id = "test_task_agg"
        self.model_manager = MockModelManager()
        self.developer = Developer(self.session_id, self.model_manager)
        self.task = Task(task_id=self.task_id, description="Test intelligent traversal")

    def test_intelligent_traversal(self):
        status, result = self.developer.orchestrate(self.task)
        self.assertIn(status, ["debugged", "tested"])  # Depending on mock behavior
        self.assertTrue(len(self.developer.tasks[self.task_id]["processed"]) > 0)
        print(f"Processed agents: {self.developer.tasks[self.task_id]['processed']}")

if __name__ == "__main__":
    unittest.main()
