from __future__ import annotations

from pathlib import Path

import pytest

from prompttest.discovery import discover_and_prepare_suites


def test_discover_raises_when_prompttests_missing(in_tmp_project: Path):
    with pytest.raises(FileNotFoundError, match="Directory 'prompttests' not found."):
        discover_and_prepare_suites()


def test_discover_merges_root_and_local_configs_and_suite_override(
    initialized_project: Path, write_suite_file
):
    content = """
config:
  prompt: customer_service
  generation_temperature: 0.6

tests:
  - id: t1
    inputs:
      user_name: "Zoë"
      user_tier: "Premium"
      product_name: "Chrono-Watch"
      user_query: "Hello"
    criteria: "expect-pass"
"""
    write_suite_file("sub/returns.yml", content)
    suites = discover_and_prepare_suites()
    files = [s.file_path for s in suites]
    assert Path("prompttests/sub/returns.yml") in files

    target = next(
        s for s in suites if s.file_path == Path("prompttests/sub/returns.yml")
    )
    assert target.config.generation_temperature == 0.6
    assert target.config.evaluation_temperature == 0.0
    assert target.config.generation_model is not None
    assert "You are a customer service agent for" in target.prompt_content


def test_discover_missing_prompt_definition_raises(
    initialized_project: Path, write_suite_file
):
    write_suite_file(
        "bad/missing_prompt.yml",
        """
config:
  generation_temperature: 0.3
tests:
  - id: a
    inputs: {}
    criteria: "x"
""",
    )
    with pytest.raises(
        ValueError,
        match=r"Suite 'prompttests/bad/missing_prompt\.yml' is missing a `prompt` definition\.",
    ):
        discover_and_prepare_suites()


def test_discover_missing_prompt_file_raises(
    initialized_project: Path, write_suite_file
):
    write_suite_file(
        "bad/missing_prompt_file.yml",
        """
config:
  prompt: does_not_exist
tests:
  - id: a
    inputs: {}
    criteria: "x"
""",
    )
    with pytest.raises(
        FileNotFoundError, match=r"Prompt file not found: prompts/does_not_exist\.txt"
    ):
        discover_and_prepare_suites()


def test_discover_invalid_yaml_reports_file(
    initialized_project: Path, write_suite_file
):
    write_suite_file(
        "bad/invalid_yaml.yml",
        """
config:
  prompt: customer_service
tests:
  - id: ok
    inputs: {}
    criteria: "x"
  - id: bad
    inputs
      foo: bar
    criteria: "y"
""",
    )
    with pytest.raises(
        ValueError,
        match=r"Error parsing YAML in prompttests/bad/invalid_yaml\.yml or its configs:",
    ):
        discover_and_prepare_suites()
