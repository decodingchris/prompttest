from __future__ import annotations

import time
from pathlib import Path

import pytest

from prompttest.cli import app


# --- Performance: ensure init scales reasonably with large .gitignore files ---
# These thresholds are intentionally generous to avoid flakiness in CI but still assert performance.


@pytest.mark.parametrize(
    "size_bytes, threshold_seconds, label",
    [
        pytest.param(512, 0.25, "small-<1KB", id="small-<1KB"),
        pytest.param(50 * 1024, 0.5, "medium-~50KB", id="medium-~50KB"),
        pytest.param(2 * 1024 * 1024, 2.0, "large-~2MB", id="large-~2MB"),
    ],
)
def test_init_performance_with_preexisting_gitignore(
    runner, in_tmp_project: Path, size_bytes: int, threshold_seconds: float, label: str
):
    gi = in_tmp_project / ".gitignore"
    # Create a large file that does not yet contain the prompttest entries
    gi.write_text("x" * (size_bytes - 1) + "\n")

    t0 = time.perf_counter()
    result = runner.invoke(app, ["init"])
    elapsed = time.perf_counter() - t0

    assert result.exit_code == 0, f"init failed for case {label}"
    assert elapsed < threshold_seconds, f"init too slow for {label}: {elapsed:.3f}s"
    # Sanity check: entries appended exactly once
    content = gi.read_text()
    assert "# prompttest cache\n.prompttest_cache/" in content
    assert "# Environment variables\n.env" in content
