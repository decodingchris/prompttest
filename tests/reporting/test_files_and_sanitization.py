from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from prompttest import reporting
from prompttest.reporting import (
    REPORTS_DIR,
    create_latest_symlink,
    create_run_directory,
)


@pytest.mark.parametrize(
    "src, expected",
    [
        ("abc/def:ghi\\jkl?.txt  ", "abc_def_ghi_jkl_.txt"),
        ("  ...name...  ", "name"),
        ('<>:":/\\|?*\\r\\n\\t', "r_n_t"),
        ('<>:":/\\|?*\r\n\t', "item"),
        ("", "item"),
        ("a__b///c.. ", "a_b_c"),
    ],
    ids=[
        "mixed-seps-and-illegal",
        "trim-dots",
        "all-illegal-literal",
        "all-illegal-control-chars",
        "empty",
        "collapse-underscores",
    ],
)
def test_sanitize_for_filename_edge_cases(src: str, expected: str, monkeypatch):
    monkeypatch.setattr(reporting.os, "altsep", "/", raising=False)
    out = reporting._sanitize_for_filename(src)
    assert out == expected


def test_create_latest_symlink_existing_symlink_unlink_failure(
    monkeypatch, in_tmp_project: Path, capsys
):
    run_dir = create_run_directory()
    create_latest_symlink(run_dir, Console())
    latest = REPORTS_DIR / "latest"
    assert latest.exists() and latest.is_symlink()

    orig_unlink = Path.unlink

    def bad_unlink(self: Path):
        if self == latest:
            raise OSError("cannot unlink")
        return orig_unlink(self)

    monkeypatch.setattr(Path, "unlink", bad_unlink)
    create_latest_symlink(run_dir, Console())
    out = capsys.readouterr().out
    assert "Warning:" in out
    assert "Could not remove existing symlink 'latest'." in out
