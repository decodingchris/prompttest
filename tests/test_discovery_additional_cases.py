from __future__ import annotations

from pathlib import Path

import pytest

import prompttest.discovery as discovery
from prompttest.discovery import discover_and_prepare_suites


def _write_min_prompt(tmp: Path, name: str = "cs") -> None:
    (tmp / "prompts").mkdir(exist_ok=True)
    (tmp / "prompts" / f"{name}.txt").write_text("Body", encoding="utf-8")


def test_duplicate_yaml_anchors_within_single_config_doc_raises(in_tmp_project: Path):
    discovery.clear_caches()
    _write_min_prompt(in_tmp_project, "cs")

    pt = in_tmp_project / "prompttests"
    pt.mkdir()
    (pt / "prompttest.yml").write_text(
        "reusable:\n  inputs:\n    a: &dupe 1\n    b: &dupe 2\n",
        encoding="utf-8",
    )
    (pt / "suite.yml").write_text(
        "config:\n  prompt: cs\ntests:\n  - id: t\n    inputs: {}\n    criteria: 'x'\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"Duplicate YAML anchor names found within .*prompttest\.yml: dupe\.",
    ):
        discover_and_prepare_suites()


def test_multi_document_config_is_not_supported_parsing_error(in_tmp_project: Path):
    discovery.clear_caches()
    _write_min_prompt(in_tmp_project, "cs")

    pt = in_tmp_project / "prompttests"
    pt.mkdir()
    (pt / "prompttest.yml").write_text(
        (
            "reusable:\n"
            "  inputs:\n"
            "    a: &x 1\n"
            "---\n"
            "reusable:\n"
            "  criteria:\n"
            "    b: &x 2\n"
        ),
        encoding="utf-8",
    )
    (pt / "suite.yml").write_text(
        "config:\n  prompt: cs\ntests:\n  - id: t\n    inputs: {}\n    criteria: 'y'\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"Error parsing YAML in prompttests/suite\.yml or its configs:",
    ):
        discover_and_prepare_suites()
