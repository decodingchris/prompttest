from __future__ import annotations

import asyncio
from pathlib import Path

from prompttest import runner


def test_runner_no_tests_found(in_tmp_project: Path, capsys):
    pdir = in_tmp_project / "prompttests"
    pdir.mkdir()
    (pdir / "prompttest.yml").write_text("config: {}", encoding="utf-8")

    code = asyncio.run(runner.run_all_tests())
    out = capsys.readouterr().out
    assert code == 0
    assert "No tests found." in out


def test_runner_discovery_value_error(in_tmp_project: Path, capsys):
    pdir = in_tmp_project / "prompttests"
    pdir.mkdir()
    (pdir / "bad.yml").write_text(
        "config:\n  prompt: customer_service\ntests:\n  - id: a\n    inputs\n      x: y\n",
        encoding="utf-8",
    )

    code = asyncio.run(runner.run_all_tests())
    out = capsys.readouterr().out
    assert code == 1
    assert "Error:" in out
