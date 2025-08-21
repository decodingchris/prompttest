from __future__ import annotations

from prompttest import discovery


def test_find_anchor_dupes_handles_ellipsis_separator_no_within_doc_dupes():
    text = (
        "reusable:\n  inputs:\n    a: &x 1\n...\nreusable:\n  criteria:\n    b: &x 2\n"
    )
    dupes = discovery._find_anchor_dupes_in_text(text)
    assert dupes == []
