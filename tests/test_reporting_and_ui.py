# tests/test_reporting_and_ui.py
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest
from rich.console import Console

from prompttest import ui
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


def _mk_result(
    *,
    suite_path: str,
    test_id: str,
    passed: bool,
    evaluation: str = "",
    error: str | None = None,
    is_cached: bool = False,
) -> PTTestResult:
    return PTTestResult(
        test_case=PTTestCase(id=test_id, inputs={}, criteria="irrelevant"),
        suite_path=Path(suite_path),
        config=Config(),
        prompt_name="p",
        rendered_prompt="rp",
        passed=passed,
        response="resp" if passed else "",
        evaluation=evaluation,
        error=error,
        is_cached=is_cached,
    )


def test_render_summary_all_pass_includes_pass_rate_and_cached(capsys):
    console = Console()
    results = [
        _mk_result(
            suite_path="prompttests/a.yml", test_id="t1", passed=True, is_cached=True
        ),
        _mk_result(
            suite_path="prompttests/a.yml", test_id="t2", passed=True, is_cached=True
        ),
        _mk_result(
            suite_path="prompttests/b.yml", test_id="t3", passed=True, is_cached=False
        ),
    ]
    ui.render_summary(console, results, elapsed_time=0.42)
    out = capsys.readouterr().out
    assert "passed" in out
    assert re.search(r"\b100% pass rate\b", out) is not None
    assert re.search(r"\b2 cached\b", out) is not None
    assert "prompttests/a.yml" not in out
    assert "prompttests/b.yml" not in out


def test_render_summary_lists_failures_with_suite_id_and_truncated_reason(capsys):
    console = Console()
    results = [
        _mk_result(
            suite_path="prompttests/a.yml",
            test_id="t1",
            passed=False,
            evaluation="First line of reason\nSecond line of reason",
        ),
        _mk_result(
            suite_path="prompttests/a.yml",
            test_id="t2",
            passed=False,
            evaluation="Only one line reason",
        ),
        _mk_result(
            suite_path="prompttests/b.yml",
            test_id="t3",
            passed=False,
            error="API returned a 503 status code from provider 'foo'.",
        ),
        _mk_result(suite_path="prompttests/c.yml", test_id="p1", passed=True),
    ]
    ui.render_summary(console, results, elapsed_time=1.23)
    out = capsys.readouterr().out

    assert "passed" in out and "failed" in out
    assert re.search(r"\b25% pass rate\b", out) is not None

    assert "prompttests/a.yml" in out
    assert "prompttests/b.yml" in out
    assert "t1" in out and "t2" in out and "t3" in out

    assert "First line of reason" in out
    assert "[...]" in out
    assert "Only one line reason" in out

    assert "API returned a 503 status code from provider 'foo'." in out


def test_render_summary_with_no_tests_prints_nothing(capsys):
    console = Console()
    ui.render_summary(console, [], elapsed_time=0.01)
    out = capsys.readouterr().out
    assert out == ""
