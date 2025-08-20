from __future__ import annotations

from pathlib import Path
from textwrap import dedent

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


def test_multi_config_distinct_anchor_names_parse_ok(in_tmp_project: Path):
    # Ensure caches are clean for this test
    discovery._read_text_cached.cache_clear()
    discovery._load_yaml_file.cache_clear()
    try:
        # Prompt needed by discovery
        PROMPTS_DIR.mkdir(exist_ok=True)
        (PROMPTS_DIR / "cs.txt").write_text("Prompt body", encoding="utf-8")

        # Root config with reusable anchors
        (in_tmp_project / "prompttests").mkdir()
        (in_tmp_project / "prompttests" / "prompttest.yml").write_text(
            dedent(
                """
                reusable:
                  inputs:
                    product_name: &prod "Chrono-Watch"
                  criteria:
                    polite: &polite >
                      Please be polite and helpful.
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        # Subdirectory config with different anchor names
        (in_tmp_project / "prompttests" / "sub").mkdir()
        (in_tmp_project / "prompttests" / "sub" / "prompttest.yml").write_text(
            dedent(
                """
                reusable:
                  inputs:
                    standard_user: &standard
                      user_name: "Alex"
                      user_tier: "Premium"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        # Suite that references anchors from both configs
        (in_tmp_project / "prompttests" / "sub" / "suite.yml").write_text(
            dedent(
                """
                config:
                  prompt: cs
                tests:
                  - id: t
                    inputs:
                      <<: *standard
                      product_name: *prod
                      user_query: "Hello"
                    criteria: *polite
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        suites = discover_and_prepare_suites()
        assert len(suites) == 1
        s = suites[0]
        assert s.file_path == Path("prompttests/sub/suite.yml")
        assert s.prompt_name == "cs"
        assert "Prompt body" in s.prompt_content

        assert len(s.tests) == 1
        t = s.tests[0]
        assert t.id == "t"
        # Anchors must be resolved into concrete values
        assert t.inputs == {
            "user_name": "Alex",
            "user_tier": "Premium",
            "product_name": "Chrono-Watch",
            "user_query": "Hello",
        }
        assert "polite and helpful" in t.criteria
    finally:
        discovery._read_text_cached.cache_clear()
        discovery._load_yaml_file.cache_clear()
