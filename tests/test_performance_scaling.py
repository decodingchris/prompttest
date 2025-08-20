from __future__ import annotations

import time
from pathlib import Path

import pytest

from prompttest.cli import app


@pytest.mark.parametrize(
    "size_bytes, threshold_seconds, label",
    [
        (512, 0.25, "small-<1KB"),
        (50 * 1024, 0.6, "medium-~50KB"),
        (2 * 1024 * 1024, 2.0, "large-~2MB"),
    ],
)
def test_init_performance_with_preexisting_gitignore(
    runner, in_tmp_project: Path, size_bytes: int, threshold_seconds: float, label: str
):
    gi = in_tmp_project / ".gitignore"
    gi.write_text("x" * (size_bytes - 1) + "\n", encoding="utf-8")

    t0 = time.perf_counter()
    res = runner.invoke(app, ["init"])
    elapsed = time.perf_counter() - t0

    assert res.exit_code == 0, f"init failed for case {label}"
    assert elapsed < threshold_seconds, f"init too slow for {label}: {elapsed:.3f}s"

    content = gi.read_text(encoding="utf-8")
    assert "# prompttest cache\n.prompttest_cache/" in content
    assert "# Test reports\n.prompttest_reports/" in content
    assert "# Environment variables\n.env" in content
