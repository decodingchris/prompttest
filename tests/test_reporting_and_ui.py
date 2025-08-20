from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from rich.console import Console

from prompttest.discovery import PROMPTS_DIR
from prompttest.models import (
    Config,
    TestCase as PTTestCase,
    TestResult as PTTestResult,
)
from prompttest.reporting import (
    REPORTS_DIR,
    create_latest_symlink,
    create_run_directory,
    write_report_file,
)
from prompttest.ui import _truncate_text, render_template_error


def test_create_run_directory_and_latest_symlink(in_tmp_project: Path):
    run1 = create_run_directory()
    assert run1.exists() and run1.is_dir()
    create_latest_symlink(run1, Console())
    latest = REPORTS_DIR / "latest"
    assert latest.exists()

    time.sleep(1.1)
    run2 = create_run_directory()
    create_latest_symlink(run2, Console())
    assert latest.exists()


def test_write_single_report_file(in_tmp_project: Path):
    (PROMPTS_DIR).mkdir(exist_ok=True)
    prompt_name = "customer_service"
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    prompt_path.write_text("Prompt body here", encoding="utf-8")

    tr = PTTestResult(
        test_case=PTTestCase(id="t-1", inputs={}, criteria="crit"),
        suite_path=Path("prompttests/suite.yml"),
        config=Config(
            generation_model="g-model",
            evaluation_model="e-model",
            generation_temperature=0.1,
            evaluation_temperature=0.0,
        ),
        prompt_name=prompt_name,
        rendered_prompt="Rendered prompt",
        passed=True,
        response="Resp",
        evaluation="OK",
    )
    run_dir = create_run_directory()
    write_report_file(tr, run_dir)
    report_path = run_dir / "suite-t-1.md"
    content = report_path.read_text(encoding="utf-8")
    assert "# ✅ Test Pass Report: `t-1`" in content
    assert "- **Generation Model**: `g-model`" in content
    assert "## Request (Prompt + Values)" in content


@pytest.mark.parametrize(
    "src, max_lines, expected",
    [
        ("a\nb\nc\nd", 3, "a\nb\nc\n[...]"),
        ("a\nb\nc", 5, "a\nb\nc"),
        ("   \na\n", 1, "a"),
    ],
)
def test_truncate_text_variants(src: str, max_lines: int, expected: str):
    assert _truncate_text(src, max_lines) == expected


def test_render_template_error_shows_filename_and_guidance(capsys):
    err = FileNotFoundError(2, "No such file", "/path/to/_env.txt")
    render_template_error(err)
    out = capsys.readouterr()
    assert "Template file not found" in out.err
    assert "_env.txt" in out.err
    assert "valid installation of prompttest" in out.err


def test_render_template_error_without_filename(capsys):
    err = FileNotFoundError("missing")
    render_template_error(err)
    out = capsys.readouterr()
    assert "Template file not found: None" in out.err


def test_create_latest_symlink_fallback(monkeypatch, in_tmp_project: Path, capsys):
    run_dir = create_run_directory()

    calls = {"count": 0}

    def fake_symlink(src, dst, target_is_directory=True):
        calls["count"] += 1
        if calls["count"] == 1:
            raise AttributeError("no symlink")
        raise OSError("nope")

    monkeypatch.setattr(os, "symlink", fake_symlink)
    create_latest_symlink(run_dir, Console())
    out = capsys.readouterr().out
    assert "Warning:" in out
