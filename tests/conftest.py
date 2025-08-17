from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest
from typer.testing import CliRunner

import prompttest.cli as cli


@pytest.fixture(scope="session")
def runner() -> CliRunner:
    # Older Click/Typer versions don't support mix_stderr. Use defaults.
    return CliRunner()


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    # The CLI reads templates relative to its own file location.
    return Path(cli.__file__).parent / "templates"


@pytest.fixture(scope="session")
def template_texts(templates_dir: Path) -> Dict[str, str]:
    # Map of target files -> expected contents from templates.
    return {
        "prompts/customer_service.txt": (
            templates_dir / "_customer_service.txt"
        ).read_text(),
        "prompttests/prompttest.yml": (
            templates_dir / "_global_config.yml"
        ).read_text(),
        "prompttests/main.yml": (templates_dir / "_main_suite.yml").read_text(),
        "prompttests/GUIDE.md": (templates_dir / "_guide.md").read_text(),
        ".env": (templates_dir / "_env.txt").read_text(),
        ".env.example": (templates_dir / "_env.txt").read_text(),
    }


@pytest.fixture()
def in_tmp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path
