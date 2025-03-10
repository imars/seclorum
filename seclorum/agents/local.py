from .framework import Agent, AgentConfig
import ollama  # Placeholder for Ollama integration

class LocalAgent(Agent):
    async def process(self, task: str, files: dict) -> str:
        # Simulate Ollama inference
        response = ollama.generate(model="llama", prompt=f"{task}\nFiles: {files}")
        return response["text"]
