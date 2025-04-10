# seclorum/agents/agent.py
from typing import Dict, Tuple, Any
from seclorum.agents.base import AbstractAgent
from seclorum.models.manager import ModelManager, create_model_manager

class Agent(AbstractAgent):
    def __init__(self, name: str, session_id: str, model_manager: ModelManager = None, model_name: str = "LLaMA-3.2-latest"):
        super().__init__(name, session_id)
        # Use provided ModelManager or create a default one
        self.model = model_manager or create_model_manager(provider="ollama", model_name=model_name)
        self.log_update(f"Agent {name} initialized with model {self.model.model_name}")

    def infer(self, prompt: str, **kwargs) -> str:
        """Run inference with the agent's model."""
        self.log_update(f"Inferring with prompt: {prompt[:50]}...")
        return self.model.generate(prompt, **kwargs)

    def process_task(self, task: "Task") -> Tuple[str, Any]:
        """Base implementation; override in subclasses."""
        raise NotImplementedError("Subclasses must implement process_task")
