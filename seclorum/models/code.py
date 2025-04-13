# seclorum/models/code.py
from pydantic import BaseModel
from typing import Optional

class CodeOutput(BaseModel):
    code: str
    tests: Optional[str] = None

class TestResult(BaseModel):
    test_code: str
    passed: bool
    output: Optional[str] = None

    # Prevent pytest from collecting as a test class
    __test__ = False

class CodeResult(BaseModel):
    test_code: str
    passed: bool
    output: Optional[str] = None

    # Prevent pytest from collecting
    __test__ = False
