from __future__ import annotations

from pathlib import Path

import pytest

from prompttest import llm as llm_mod
from prompttest import runner


@pytest.mark.asyncio
async def test_runner_error_missing_generation_model(
    monkeypatch, in_tmp_project: Path, capsys, write_prompt_file
):
    write_prompt_file("cs", "Hello {name}")
    Path("prompttests").mkdir()
    Path("prompttests/s1.yml").write_text(
        "config:\n  prompt: cs\n  evaluation_model: 'judge'\n"
        "tests:\n  - id: t\n    inputs: {name: 'A'}\n    criteria: 'c'\n",
        encoding="utf-8",
    )

    code = await runner.run_all_tests()
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL: t" in out or "❌ FAIL: t" in out
    assert "generation_model" in out


@pytest.mark.asyncio
async def test_runner_error_missing_evaluation_model(
    monkeypatch, in_tmp_project: Path, capsys, write_prompt_file
):
    write_prompt_file("cs", "Hello {name}")
    Path("prompttests").mkdir()
    Path("prompttests/s2.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: 'gen'\n"
        "tests:\n  - id: t\n    inputs: {name: 'B'}\n    criteria: 'c'\n",
        encoding="utf-8",
    )

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "resp", False

    monkeypatch.setattr(llm_mod, "generate", fake_gen)

    code = await runner.run_all_tests()
    out = capsys.readouterr().out
    assert code == 1
    assert "FAIL: t" in out or "❌ FAIL: t" in out
    assert "evaluation_model" in out


@pytest.mark.asyncio
async def test_runner_filters_by_test_file_globs(
    monkeypatch, in_tmp_project: Path, write_prompt_file
):
    write_prompt_file("cs", "Hello {name}")
    Path("prompttests").mkdir()
    Path("prompttests/a.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n  - id: ta\n    inputs: {name: 'A'}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )
    Path("prompttests/sub").mkdir()
    Path("prompttests/sub/b.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n  - id: tb\n    inputs: {name: 'B'}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )
    Path("prompttests/c.yaml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n  - id: tc\n    inputs: {name: 'C'}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )

    async def ok_gen(*a, **k):
        return "resp", False

    async def ok_eval(*a, **k):
        return True, "ok", False

    monkeypatch.setattr(llm_mod, "generate", ok_gen)
    monkeypatch.setattr(llm_mod, "evaluate", ok_eval)

    code = await runner.run_all_tests(test_file_globs=["sub/*.yml"])
    assert code == 0

    code = await runner.run_all_tests(test_file_globs=["c.yaml"])
    assert code == 0

    code = await runner.run_all_tests(test_file_globs=["a.yml"])
    assert code == 0


@pytest.mark.asyncio
async def test_runner_filters_by_test_id_globs(
    monkeypatch, in_tmp_project: Path, capsys, write_prompt_file
):
    write_prompt_file("cs", "Hello {name}")
    Path("prompttests").mkdir()
    Path("prompttests/ids.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n"
        "  - id: check-pass-1\n    inputs: {}\n    criteria: 'pass'\n"
        "  - id: check-fail-1\n    inputs: {}\n    criteria: 'fail'\n"
        "  - id: other-pass-2\n    inputs: {}\n    criteria: 'pass'\n",
        encoding="utf-8",
    )

    async def ok_gen(*a, **k):
        return "resp", False

    async def selective_eval(response, criteria, model, temperature):
        return ("pass" in criteria), "reason", False

    monkeypatch.setattr(llm_mod, "generate", ok_gen)
    monkeypatch.setattr(llm_mod, "evaluate", selective_eval)

    code = await runner.run_all_tests(test_id_globs=["check-*"])
    assert code == 1

    code = await runner.run_all_tests(test_id_globs=["*-1"])
    assert code == 1

    code = await runner.run_all_tests(test_id_globs=["*pass*"])
    assert code == 0


@pytest.mark.asyncio
async def test_runner_bounded_concurrency_path_executes(
    monkeypatch, in_tmp_project: Path, write_prompt_file
):
    write_prompt_file("cs", "Hello {name}")
    Path("prompttests").mkdir()
    Path("prompttests/conc.yml").write_text(
        "config:\n  prompt: cs\n  generation_model: g\n  evaluation_model: e\n"
        "tests:\n  - id: t1\n    inputs: {}\n    criteria: 'ok'\n"
        "  - id: t2\n    inputs: {}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )

    async def ok_gen(*a, **k):
        return "resp", False

    async def ok_eval(*a, **k):
        return True, "ok", False

    monkeypatch.setattr(llm_mod, "generate", ok_gen)
    monkeypatch.setattr(llm_mod, "evaluate", ok_eval)

    code = await runner.run_all_tests(max_concurrency=1)
    assert code == 0
