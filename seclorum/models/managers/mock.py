# seclorum/models/model_managers/mock.py
from ..manager import ModelManager

class MockModelManager(ModelManager):
    def __init__(self, model_name: str = "mock"):
        super().__init__(model_name, provider="mock")

    def generate(self, prompt: str, **kwargs) -> str:
        if "Generate Python code" in prompt:
            return "import os\ndef list_py_files():\n    return [f for f in os.listdir('.') if f.endswith('.py')]"
        elif "Generate a Python unit test" in prompt:
            return "import unittest\ndef test_list_files():\n    files = [f for f in os.listdir('.') if f.endswith('.py')]\n    assert isinstance(files, list)"
        return "Mock response"
