# src/prompttest/discovery.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import Config, TestCase, TestSuite

PROMPTTESTS_DIR = Path("prompttests")
PROMPTS_DIR = Path("prompts")


def _deep_merge(source: dict, destination: dict) -> dict:
    """Recursively merge dictionaries, with values from 'source' overwriting 'destination'."""
    for key, value in source.items():
        if (
            isinstance(value, dict)
            and key in destination
            and isinstance(destination[key], dict)
        ):
            destination[key] = _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


def _get_config_file_paths(start_path: Path) -> List[Path]:
    """Finds all prompttest.yml files from the start_path up to the root."""
    paths_to_check = []
    current_dir = start_path.parent
    stop_dir = PROMPTTESTS_DIR.resolve().parent

    while current_dir != stop_dir and PROMPTTESTS_DIR.name in str(current_dir):
        config_path = current_dir / "prompttest.yml"
        if config_path.is_file():
            paths_to_check.append(config_path)
        current_dir = current_dir.parent
    return list(reversed(paths_to_check))


def discover_and_prepare_suites() -> List[TestSuite]:
    if not PROMPTTESTS_DIR.is_dir():
        raise FileNotFoundError(f"Directory '{PROMPTTESTS_DIR}' not found.")

    suites = []
    suite_files = list(PROMPTTESTS_DIR.rglob("*.yml")) + list(
        PROMPTTESTS_DIR.rglob("*.yaml")
    )

    for suite_file in suite_files:
        if suite_file.name == "prompttest.yml":
            continue

        config_paths = _get_config_file_paths(suite_file)

        def _indent_block(s: str, spaces: int = 2) -> str:
            pad = " " * spaces
            return "\n".join((pad + line if line else line) for line in s.splitlines())

        if config_paths:
            anchors_prelude = "__anchors__:\n" + "\n".join(
                _indent_block(p.read_text(encoding="utf-8")) for p in config_paths
            )
        else:
            anchors_prelude = "__anchors__: {}\n"

        single_doc_text = (
            anchors_prelude + "\n" + suite_file.read_text(encoding="utf-8")
        )

        try:
            parsed_single: Dict[str, Any] = (
                yaml.load(single_doc_text, Loader=yaml.FullLoader) or {}
            )
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing YAML in {suite_file} or its configs: {e}"
            ) from e

        merged_config_data: Dict[str, Any] = {}
        for cp in config_paths:
            doc = (
                yaml.load(cp.read_text(encoding="utf-8"), Loader=yaml.FullLoader) or {}
            )
            merged_config_data = _deep_merge(doc.get("config", {}), merged_config_data)

        merged_config_data = _deep_merge(
            parsed_single.get("config", {}) or {}, merged_config_data
        )
        suite_config = Config(**merged_config_data)

        prompt_name = merged_config_data.get("prompt")
        if not prompt_name:
            raise ValueError(f"Suite '{suite_file}' is missing a `prompt` definition.")

        prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        prompt_content = prompt_path.read_text(encoding="utf-8")
        test_cases = [TestCase(**t) for t in (parsed_single.get("tests") or [])]

        if test_cases:
            suites.append(
                TestSuite(
                    file_path=suite_file,
                    config=suite_config,
                    tests=test_cases,
                    prompt_name=prompt_name,
                    prompt_content=prompt_content,
                )
            )
    return suites
