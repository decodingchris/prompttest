from __future__ import annotations

from pathlib import Path

import pytest

from prompttest import runner
from prompttest.discovery import PROMPTS_DIR


def _write_prompt(name: str = "cs"):
    PROMPTS_DIR.mkdir(exist_ok=True)
    (PROMPTS_DIR / f"{name}.txt").write_text("Hello {x}", encoding="utf-8")


@pytest.mark.asyncio
async def test_runner_file_not_found_for_missing_prompt_not_init_branch(
    in_tmp_project: Path, capsys
):
    Path("prompttests").mkdir()
    Path("prompttests/bad.yml").write_text(
        "config:\n  prompt: missing\n"
        "tests:\n  - id: t\n    inputs: {}\n    criteria: 'x'\n",
        encoding="utf-8",
    )
    code = await runner.run_all_tests()
    out = capsys.readouterr().out
    assert code == 1
    assert "Error:" in out
    assert "Prompt file not found: prompts/missing.txt" in out


@pytest.mark.asyncio
async def test_runner_test_id_globs_no_match_prints_no_tests_found(
    monkeypatch, in_tmp_project: Path, capsys
):
    _write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/one.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n  - id: alpha\n    inputs: {}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )

    async def ok_gen(*a, **k):
        return "resp", False

    async def ok_eval(*a, **k):
        return True, "ok", False

    from prompttest import llm as llm_mod

    monkeypatch.setattr(llm_mod, "generate", ok_gen)
    monkeypatch.setattr(llm_mod, "evaluate", ok_eval)

    code = await runner.run_all_tests(test_id_globs=["does-not-match-*"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No tests found." in out


@pytest.mark.asyncio
async def test_runner_unlimited_concurrency_path(monkeypatch, in_tmp_project: Path):
    _write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/multi.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n"
        "  - id: t1\n    inputs: {}\n    criteria: 'ok'\n"
        "  - id: t2\n    inputs: {}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )

    async def ok_gen(*a, **k):
        return "resp", False

    async def ok_eval(*a, **k):
        return True, "ok", False

    from prompttest import llm as llm_mod

    monkeypatch.setattr(llm_mod, "generate", ok_gen)
    monkeypatch.setattr(llm_mod, "evaluate", ok_eval)

    code = await runner.run_all_tests(max_concurrency=0)
    assert code == 0
