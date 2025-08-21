from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Config(BaseModel):
    generation_model: Optional[str] = None
    evaluation_model: Optional[str] = None
    generation_temperature: float = 0.0
    evaluation_temperature: float = 0.0


class TestCase(BaseModel):
    id: str
    inputs: Dict[str, Any] = Field(default_factory=dict)
    criteria: str


class TestSuite(BaseModel):
    file_path: Path
    config: Config = Field(default_factory=Config)
    tests: List[TestCase] = Field(default_factory=list)
    prompt_name: str
    prompt_content: str


class TestResult(BaseModel):
    test_case: TestCase
    suite_path: Path
    config: Config
    prompt_name: str
    rendered_prompt: str
    passed: bool
    response: str
    evaluation: str
    error: Optional[str] = None
    is_cached: bool = False
    error_kind: Optional[str] = None
