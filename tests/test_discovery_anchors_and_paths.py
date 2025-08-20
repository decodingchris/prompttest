from __future__ import annotations

from pathlib import Path

import pytest

import prompttest.discovery as discovery
from prompttest.discovery import PROMPTS_DIR, discover_and_prepare_suites


def test_duplicate_yaml_anchors_across_configs(in_tmp_project: Path):
    discovery._read_text_cached.cache_clear()
    discovery._load_yaml_file.cache_clear()

    try:
        PROMPTS_DIR.mkdir(exist_ok=True)
        (PROMPTS_DIR / "cs.txt").write_text("Prompt", encoding="utf-8")

        (in_tmp_project / "prompttests").mkdir()
        (in_tmp_project / "prompttests" / "prompttest.yml").write_text(
            "reusable:\n  inputs:\n    val: &dupe 1\n", encoding="utf-8"
        )
        (in_tmp_project / "prompttests" / "sub").mkdir()
        (in_tmp_project / "prompttests" / "sub" / "prompttest.yml").write_text(
            "reusable:\n  inputs:\n    val2: &dupe 2\n", encoding="utf-8"
        )
        (in_tmp_project / "prompttests" / "sub" / "suite.yml").write_text(
            "config:\n  prompt: cs\ntests:\n  - id: t\n    inputs: {}\n    criteria: 'x'\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="Duplicate YAML anchor names found"):
            discover_and_prepare_suites()
    finally:
        discovery._read_text_cached.cache_clear()
        discovery._load_yaml_file.cache_clear()
