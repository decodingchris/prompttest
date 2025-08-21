from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Dict, Iterator, Tuple

import pytest
from typer.testing import CliRunner

import prompttest.cli as cli
from prompttest import llm
from prompttest.llm import _get_cache_key, _write_cache


@pytest.fixture(scope="session")
def runner() -> CliRunner:
    # Typer runner for CLI tests
    return CliRunner()


@pytest.fixture()
def in_tmp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Start all tests in a fresh tmp directory as CWD
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def ensure_clean_cache_and_reports(in_tmp_project: Path) -> Iterator[None]:
    # Ensure no leftovers from prior runs
    cache_dir = in_tmp_project / ".prompttest_cache"
    reports_dir = in_tmp_project / ".prompttest_reports"
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
    yield
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    if reports_dir.exists():
        shutil.rmtree(reports_dir)


@pytest.fixture(scope="session")
def templates_dir() -> Path:
    # The CLI reads templates from package
    return Path(cli.__file__).parent / "templates"


@pytest.fixture(scope="session")
def template_texts(templates_dir: Path) -> Dict[str, str]:
    # Map expected scaffolded files -> template contents
    return {
        "prompts/customer_service.txt": (
            templates_dir / "_customer_service.txt"
        ).read_text(encoding="utf-8"),
        "prompttests/prompttest.yml": (templates_dir / "_global_config.yml").read_text(
            encoding="utf-8"
        ),
        "prompttests/main.yml": (templates_dir / "_main_suite.yml").read_text(
            encoding="utf-8"
        ),
        "prompttests/GUIDE.md": (templates_dir / "_guide.md").read_text(
            encoding="utf-8"
        ),
        ".env": (templates_dir / "_env.txt").read_text(encoding="utf-8"),
        ".env.example": (templates_dir / "_env.txt").read_text(encoding="utf-8"),
    }


@pytest.fixture()
def initialized_project(
    in_tmp_project: Path, runner: CliRunner, template_texts: Dict[str, str]
) -> Path:
    # Run 'prompttest init' to scaffold
    result = runner.invoke(cli.app, ["init"])
    assert result.exit_code == 0, f"Init failed: {result.stdout}"
    # Verify expected files exist
    for rel_path, expected in template_texts.items():
        p = in_tmp_project / rel_path
        assert p.exists(), f"Missing {rel_path}"
        assert p.read_text(encoding="utf-8") == expected
    return in_tmp_project


@pytest.fixture()
def mock_llm_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock llm.generate / llm.evaluate to always pass
    async def fake_generate(
        prompt: str, model: str, temperature: float
    ) -> Tuple[str, bool]:
        return f"[GEN:{model}|{temperature}] {prompt[:40]}", False

    async def fake_evaluate(
        response: str, criteria: str, model: str, temperature: float
    ) -> Tuple[bool, str, bool]:
        return True, "Meets criteria", False

    monkeypatch.setattr(llm, "generate", fake_generate)
    monkeypatch.setattr(llm, "evaluate", fake_evaluate)


@pytest.fixture()
def mock_llm_selective(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock llm.evaluate to pass/fail based on criteria content; generate returns minimal
    async def fake_generate(
        prompt: str, model: str, temperature: float
    ) -> Tuple[str, bool]:
        return f"response for model={model} temp={temperature}", False

    async def fake_evaluate(
        response: str, criteria: str, model: str, temperature: float
    ) -> Tuple[bool, str, bool]:
        if "expect-pass" in criteria:
            return True, "PASS as requested", False
        return False, "FAIL as requested", False

    monkeypatch.setattr(llm, "generate", fake_generate)
    monkeypatch.setattr(llm, "evaluate", fake_evaluate)


@pytest.fixture()
def cache_primed() -> Iterator[None]:
    CACHE_DIR = Path(".prompttest_cache")
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    CACHE_DIR.mkdir(exist_ok=True)
    yield
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)


@pytest.fixture()
def prime_generate_cache(
    cache_primed: None,
) -> Callable[[str, str, float, str], None]:
    # Helper to put an entry into the generate() cache
    def _prime(prompt: str, model: str, temperature: float, content: str) -> None:
        key = _get_cache_key(
            {"prompt": prompt, "model": model, "temperature": temperature}
        )
        _write_cache(key, content)

    return _prime


@pytest.fixture()
def prime_evaluate_cache(
    cache_primed: None,
) -> Callable[[str, str, float, str, Dict[str, object]], None]:
    # Helper to put an entry into the structured evaluate() cache
    def _prime(
        criteria: str,
        model: str,
        temperature: float,
        response: str,
        verdict_json: Dict[str, object],
    ) -> None:
        prompt = (
            "Criteria:\n"
            f"{criteria}\n\n"
            "Response:\n"
            f"{response}\n\n"
            "Decide if the response meets the criteria."
        )
        key = _get_cache_key(
            {
                "v": 2,
                "mode": "structured",
                "eval_prompt": prompt,
                "model": model,
                "temperature": temperature,
            }
        )
        _write_cache(key, json.dumps(verdict_json))

    return _prime


@pytest.fixture()
def write_suite_file(in_tmp_project: Path) -> Callable[[str, str], Path]:
    # Utility to write a test suite file into prompttests/
    def _write(rel_path: str, content: str) -> Path:
        dst = in_tmp_project / "prompttests" / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        return dst

    return _write


@pytest.fixture()
def write_prompt_file(in_tmp_project: Path) -> Callable[[str, str], Path]:
    # Utility to write a prompt template into prompts/
    def _write(name_without_ext: str, content: str) -> Path:
        dst = in_tmp_project / "prompts" / f"{name_without_ext}.txt"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        return dst

    return _write
