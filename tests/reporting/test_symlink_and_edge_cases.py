from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from rich.console import Console

from prompttest import reporting
from prompttest.reporting import (
    REPORTS_DIR,
    create_latest_symlink,
    create_run_directory,
)


def test_create_run_directory_collision_same_timestamp(
    monkeypatch, in_tmp_project: Path
):
    class FixedDatetime:
        @staticmethod
        def now():
            return datetime(2025, 1, 1, 0, 0, 0, 0)

    monkeypatch.setattr(reporting, "datetime", FixedDatetime)

    run1 = create_run_directory()
    assert run1.exists()
    run2 = create_run_directory()
    assert run2.exists()
    assert run2.name.startswith(run1.name)
    assert run2.name != run1.name
    assert any(part.endswith("-1") for part in [run2.name])
    create_latest_symlink(run2, Console())
    assert (REPORTS_DIR / "latest").exists()


def test_create_latest_symlink_replaces_empty_dir(in_tmp_project: Path):
    run_dir = create_run_directory()
    latest = REPORTS_DIR / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    assert latest.is_dir() and not latest.is_symlink()

    create_latest_symlink(run_dir, Console())

    assert latest.exists()
    assert latest.is_symlink()


def test_create_latest_symlink_warns_on_nonempty_dir(in_tmp_project: Path, capsys):
    run_dir = create_run_directory()
    latest = REPORTS_DIR / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    (latest / "keep.txt").write_text("x", encoding="utf-8")

    create_latest_symlink(run_dir, Console())
    out = capsys.readouterr().out

    assert "Warning:" in out
    assert "Cannot replace existing 'latest'" in out
    assert latest.exists() and latest.is_dir()


def test_create_latest_symlink_replaces_file(in_tmp_project: Path):
    run_dir = create_run_directory()
    latest = REPORTS_DIR / "latest"
    latest.write_text("x", encoding="utf-8")

    create_latest_symlink(run_dir, Console())

    assert latest.exists()
    assert latest.is_symlink()


def test_create_run_directory_and_latest_symlink(in_tmp_project: Path):
    run1 = create_run_directory()
    assert run1.exists() and run1.is_dir()
    create_latest_symlink(run1, Console())
    latest = REPORTS_DIR / "latest"
    assert latest.exists()

    # Ensure a different timestamp on the next run directory
    run2 = create_run_directory()
    create_latest_symlink(run2, Console())
    assert latest.exists()


def test_create_latest_symlink_fallback(monkeypatch, in_tmp_project: Path, capsys):
    run_dir = create_run_directory()
    calls = {"n": 0}

    def fake_symlink(src, dst, target_is_directory=True):
        calls["n"] += 1
        if calls["n"] == 1:
            # First attempt should simulate environments without symlink support
            raise AttributeError("no symlink")
        # Second attempt should simulate OS-level failure
        raise OSError("nope")

    monkeypatch.setattr(os, "symlink", fake_symlink)
    create_latest_symlink(run_dir, Console())
    out = capsys.readouterr().out
    assert "Warning:" in out
