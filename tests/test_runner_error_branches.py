from __future__ import annotations

import asyncio
from pathlib import Path


from prompttest import llm, runner


def _write_suite(tmp: Path, name="suite.yml") -> Path:
    d = tmp / "prompttests"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text(
        "config:\n  prompt: customer_service\n"
        "tests:\n"
        "  - id: t1\n    inputs: {}\n    criteria: 'x'\n",
        encoding="utf-8",
    )
    pd = tmp / "prompts"
    pd.mkdir(exist_ok=True)
    (pd / "customer_service.txt").write_text("Hello {name}", encoding="utf-8")
    return p


def test_runner_generate_llmerror(monkeypatch, in_tmp_project: Path, capsys):
    _write_suite(in_tmp_project)

    class E(llm.LLMError):
        pass

    async def bad_generate(*a, **k):
        raise E("boom-gen")

    monkeypatch.setattr(llm, "generate", bad_generate)

    async def ok_eval(*a, **k):
        return True, "ok", False

    monkeypatch.setattr(llm, "evaluate", ok_eval)

    code = asyncio.run(runner.run_all_tests())
    out = capsys.readouterr().out
    assert code == 1
    assert "API Error" in out or "Error:" in out


def test_runner_evaluate_llmerror(monkeypatch, in_tmp_project: Path, capsys):
    _write_suite(in_tmp_project)

    async def ok_generate(*a, **k):
        return "resp", False

    monkeypatch.setattr(llm, "generate", ok_generate)

    class E(llm.LLMError):
        pass

    async def bad_evaluate(*a, **k):
        raise E("boom-eval")

    monkeypatch.setattr(llm, "evaluate", bad_evaluate)

    code = asyncio.run(runner.run_all_tests())
    out = capsys.readouterr().out
    assert code == 1
    assert "API Error" in out or "Error:" in out
