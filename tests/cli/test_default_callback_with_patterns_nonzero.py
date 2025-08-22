from __future__ import annotations

from typing import Any, Dict

from typer.testing import CliRunner

import prompttest.cli as cli_mod
from prompttest.cli import app


def test_run_command_forwards_positional_patterns_and_propagates_exit_code(
    monkeypatch, runner: CliRunner, in_tmp_project
):
    captured: Dict[str, Any] = {}

    async def fake_run_all_tests(**kwargs) -> int:
        captured.update(kwargs)
        return 5

    monkeypatch.setattr(cli_mod.runner, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, ["run", "suite*.yml", "check-*"])
    assert res.exit_code == 5

    assert "test_file_globs" in captured
    assert "suite*.yml" in captured["test_file_globs"]
    assert "**/suite*.yml" in captured["test_file_globs"]
    assert captured["test_id_globs"] == ["check-*"]
