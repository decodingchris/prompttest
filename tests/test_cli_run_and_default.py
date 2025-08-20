from __future__ import annotations

from pathlib import Path
from typing import List

from prompttest import runner as runner_mod
from prompttest.cli import app


def test_prompttest_without_args_invokes_run_command(
    monkeypatch, runner, in_tmp_project: Path
):
    called: List[int] = []

    async def fake_run_all_tests() -> int:
        called.append(1)
        return 0

    monkeypatch.setattr(runner_mod, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, [])
    assert res.exit_code == 0
    assert called == [1]


def test_prompttest_run_command_explicit(monkeypatch, runner, in_tmp_project: Path):
    async def fake_run_all_tests() -> int:
        return 0

    monkeypatch.setattr(runner_mod, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, ["run"])
    assert res.exit_code == 0


def test_prompttest_run_nonzero_exit_propagates(
    monkeypatch, runner, in_tmp_project: Path
):
    async def fake_run_all_tests() -> int:
        return 3

    monkeypatch.setattr(runner_mod, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, ["run"])
    assert res.exit_code == 3
