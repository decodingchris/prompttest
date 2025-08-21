from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from typer.testing import CliRunner

import prompttest.cli as cli_mod
from prompttest import discovery
from prompttest import runner as runner_mod
from prompttest.cli import app


def test_classify_patterns_variants(monkeypatch, in_tmp_project: Path):
    pt = in_tmp_project / "prompttests"
    pt.mkdir()
    (pt / "alpha").mkdir()
    (pt / "beta").mkdir()
    (pt / "alpha" / "test.yml").write_text("config:\n  prompt: x\n", encoding="utf-8")
    (pt / "beta" / "sample.yaml").write_text("config:\n  prompt: y\n", encoding="utf-8")

    monkeypatch.setattr(discovery, "PROMPTTESTS_DIR", pt)

    file_globs, id_globs = cli_mod._classify_patterns(
        ["test", "alpha/test.yml", "zzz", "beta/sample.yaml", "custom.yaml"]
    )

    assert "**/test.yml" in file_globs
    assert "**/test.yaml" in file_globs
    assert "alpha/test.yml" in file_globs
    assert "beta/sample.yaml" in file_globs
    assert "custom.yaml" in file_globs and "**/custom.yaml" in file_globs
    assert "zzz" in id_globs


def test_classify_patterns_when_prompttests_missing(monkeypatch, in_tmp_project: Path):
    pt = in_tmp_project / "prompttests"
    if pt.exists():
        pt.rmdir()
    monkeypatch.setattr(discovery, "PROMPTTESTS_DIR", pt)

    files, ids = cli_mod._classify_patterns(["abc", "suite.yml"])
    assert files == ["**/suite.yml", "suite.yml"]
    assert ids == ["abc"]


def test_run_command_forwards_options(
    monkeypatch, runner: CliRunner, in_tmp_project: Path
):
    captured: Dict[str, Any] = {}

    async def fake_run_all_tests(**kwargs) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(runner_mod, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(
        app,
        [
            "run",
            "--test-file",
            "sub/*.yml",
            "--test-file",
            "x.yml",
            "--test-id",
            "check-*",
            "--test-id",
            "t*",
            "--max-concurrency",
            "1",
        ],
    )
    assert res.exit_code == 0
    assert captured["test_file_globs"] == ["sub/*.yml", "x.yml"]
    assert captured["test_id_globs"] == ["check-*", "t*"]
    assert captured["max_concurrency"] == 1


def test_run_command_forwards_positional_patterns(
    monkeypatch, runner: CliRunner, in_tmp_project: Path
):
    captured: Dict[str, Any] = {}

    async def fake_run_all_tests(**kwargs) -> int:
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(runner_mod, "run_all_tests", fake_run_all_tests)
    res = runner.invoke(app, ["run", "suite-*.yml", "check-*"])
    assert res.exit_code == 0

    assert "test_file_globs" in captured
    assert "suite-*.yml" in captured["test_file_globs"]
    assert "**/suite-*.yml" in captured["test_file_globs"]
    assert captured["test_id_globs"] == ["check-*"]
