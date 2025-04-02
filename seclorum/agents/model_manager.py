# seclorum/agents/model_manager.py
import ollama

class ModelManager:
    def __init__(self, model_name: str = "llama3.2:1b"):
        self.model_name = model_name
        # Initialize model here if needed; Ollama handles this internally for now

    def generate(self, prompt: str) -> str:
        response = ollama.generate(model=self.model_name, prompt=prompt)
        return response["response"].strip()
