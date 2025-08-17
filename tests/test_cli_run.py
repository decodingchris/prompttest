from __future__ import annotations

from pathlib import Path

from prompttest.cli import app


# --- The run command and default invocation UX ---


def test_prompttest_without_args_invokes_run_command(runner, in_tmp_project: Path):
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "TODO: Implement the run command." in result.stdout


def test_prompttest_run_command_explicit(runner, in_tmp_project: Path):
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "TODO: Implement the run command." in result.stdout
