from __future__ import annotations

from pathlib import Path
from typing import List

from typer.testing import CliRunner

import prompttest.cli as cli_mod
from prompttest import discovery
from prompttest.cli import app


def test_default_callback_nonzero_exit_propagates(
    monkeypatch, runner: CliRunner, in_tmp_project: Path
):
    called: List[int] = []

    async def fake_run_all_tests() -> int:
        called.append(1)
        return 2

    monkeypatch.setattr(cli_mod.runner, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, [])
    assert res.exit_code == 2
    assert called == [1]


def test_classify_patterns_subpath_without_extension(monkeypatch, in_tmp_project: Path):
    pt = in_tmp_project / "prompttests"
    (pt / "gamma").mkdir(parents=True)
    (pt / "gamma" / "sample.yml").write_text("config:\n  prompt: x\n", encoding="utf-8")
    monkeypatch.setattr(discovery, "PROMPTTESTS_DIR", pt)

    files, ids = cli_mod._classify_patterns(["gamma/sample"])
    assert files == ["gamma/sample.yml"]
    assert ids == []


def test_classify_patterns_none_is_treated_as_empty(monkeypatch, in_tmp_project: Path):
    pt = in_tmp_project / "prompttests"
    pt.mkdir()
    monkeypatch.setattr(discovery, "PROMPTTESTS_DIR", pt)
    files, ids = cli_mod._classify_patterns(None or [])
    assert files == []
    assert ids == []
