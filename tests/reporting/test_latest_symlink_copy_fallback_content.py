from __future__ import annotations

import os
from pathlib import Path

from rich.console import Console

from prompttest.reporting import (
    REPORTS_DIR,
    create_latest_symlink,
    create_run_directory,
)


def test_create_latest_symlink_copytree_fallback_copies_contents(
    monkeypatch, in_tmp_project: Path
):
    run_dir = create_run_directory()
    (run_dir / "proof.txt").write_text("hello", encoding="utf-8")

    def always_fail_symlink(*a, **k):
        raise OSError("no symlink")

    monkeypatch.setattr(os, "symlink", always_fail_symlink)

    create_latest_symlink(run_dir, Console())

    latest = REPORTS_DIR / "latest"
    assert latest.exists()
    assert latest.is_dir()
    assert (latest / "proof.txt").read_text(encoding="utf-8") == "hello"
