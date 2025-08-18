# src/prompttest/models.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    generation_model: Optional[str] = None
    evaluation_model: Optional[str] = None
    temperature: float = 0.0


class TestCase(BaseModel):
    id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    criteria: str


class TestSuite(BaseModel):
    # The Path to the original .yml file
    file_path: Path
    # The resolved config after merging hierarchy
    config: Config = Field(default_factory=Config)
    # The list of test cases to run
    tests: List[TestCase] = Field(default_factory=list)
    # The name of the prompt file (e.g., "customer_service")
    prompt_name: str
    # The content of the prompt template
    prompt_content: str


class TestResult(BaseModel):
    test_case: TestCase
    suite_path: Path
    passed: bool
    response: str
    evaluation: str
    error: Optional[str] = None
    is_cached: bool = False
