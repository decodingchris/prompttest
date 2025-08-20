from __future__ import annotations

from datetime import datetime
from pathlib import Path

from rich.console import Console

from prompttest import reporting
from prompttest.reporting import REPORTS_DIR


def test_create_run_directory_collision_same_timestamp(
    monkeypatch, in_tmp_project: Path
):
    class FixedDatetime:
        @staticmethod
        def now():
            return datetime(2025, 1, 1, 0, 0, 0, 0)

    monkeypatch.setattr(reporting, "datetime", FixedDatetime)

    run1 = reporting.create_run_directory()
    assert run1.exists()
    run2 = reporting.create_run_directory()
    assert run2.exists()
    assert run2.name.startswith(run1.name)
    assert run2.name != run1.name
    assert any(part.endswith("-1") for part in [run2.name])
    reporting.create_latest_symlink(run2, Console())
    assert (REPORTS_DIR / "latest").exists()
