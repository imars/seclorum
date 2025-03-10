from pydantic import BaseModel
from typing import Optional

class AgentConfig(BaseModel):
    name: str
    description: Optional[str] = None

class Agent:
    def __init__(self, config: AgentConfig):
        self.config = config

    async def process(self, task: str, files: dict) -> str:
        raise NotImplementedError
