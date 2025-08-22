from __future__ import annotations

import re
from functools import lru_cache
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
    """Finds all prompttest.yml/yaml files from the start_path up to the root."""
    paths_to_check: List[Path] = []
    current_dir = start_path.parent.resolve()
    prompttests_root = PROMPTTESTS_DIR.resolve()
    top_dir = prompttests_root.parent

    while True:
        if not (
            current_dir == prompttests_root or prompttests_root in current_dir.parents
        ):
            break
        if current_dir == top_dir:
            break

        for cfg_name in ("prompttest.yml", "prompttest.yaml"):
            config_path = current_dir / cfg_name
            if config_path.is_file():
                paths_to_check.append(config_path)

        if current_dir == current_dir.parent:
            break
        current_dir = current_dir.parent

    return list(reversed(paths_to_check))


@lru_cache(maxsize=None)
def _read_text_cached(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _load_yaml_file(p: Path) -> Dict[str, Any]:
    return yaml.safe_load(_read_text_cached(p)) or {}


def _find_anchors(yaml_text: str) -> set[str]:
    return set(re.findall(r"&([A-Za-z0-9_-]+)", yaml_text))


def _find_anchor_dupes_in_text(yaml_text: str) -> list[str]:
    """
    Return anchor names that appear more than once within any single YAML document.
    A single file may contain multiple YAML documents separated by '---' or '...'.
    """
    docs = re.split(r"(?m)^(?:---|\.\.\.)\s*$", yaml_text)
    dupes: set[str] = set()
    for doc in docs:
        names = re.findall(r"&([A-Za-z0-9_-]+)", doc)
        if not names:
            continue
        counts: dict[str, int] = {}
        for n in names:
            counts[n] = counts.get(n, 0) + 1
        for n, c in counts.items():
            if c > 1:
                dupes.add(n)
    return list(dupes)


def discover_and_prepare_suites() -> List[TestSuite]:
    if not PROMPTTESTS_DIR.is_dir():
        raise FileNotFoundError(f"Directory '{PROMPTTESTS_DIR}' not found.")

    suites = []
    suite_files = list(PROMPTTESTS_DIR.rglob("*.yml")) + list(
        PROMPTTESTS_DIR.rglob("*.yaml")
    )

    suite_files.sort()

    for suite_file in suite_files:
        if suite_file.name in ("prompttest.yml", "prompttest.yaml"):
            continue

        config_paths = _get_config_file_paths(suite_file)

        def _indent_block(s: str, spaces: int = 2) -> str:
            pad = " " * spaces
            return "\n".join((pad + line if line else line) for line in s.splitlines())

        if config_paths:
            texts = [_read_text_cached(p) for p in config_paths]

            for p, txt in zip(config_paths, texts):
                local_dupes = _find_anchor_dupes_in_text(txt)
                if local_dupes:
                    dlist = ", ".join(sorted(set(local_dupes)))
                    raise ValueError(
                        f"Duplicate YAML anchor names found within {p}: {dlist}. "
                        "Anchors must be unique within each config file."
                    )

            seen: dict[str, Path] = {}
            dupes: List[tuple[str, Path, Path]] = []
            for p, txt in zip(config_paths, texts):
                for a in _find_anchors(txt):
                    if a in seen:
                        dupes.append((a, seen[a], p))
                    else:
                        seen[a] = p
            if dupes:
                lines = "\n".join(f"- {a}: {p1} and {p2}" for a, p1, p2 in dupes)
                raise ValueError(
                    "Duplicate YAML anchor names found across config files.\n"
                    "Anchors must be unique within a suite. Rename the conflicting anchors:\n"
                    f"{lines}"
                )
            anchors_prelude = "__anchors__:\n" + "\n".join(
                _indent_block(txt) for txt in texts
            )
        else:
            anchors_prelude = "__anchors__: {}\n"

        single_doc_text = anchors_prelude + "\n" + _read_text_cached(suite_file)

        try:
            parsed_single: Dict[str, Any] = yaml.safe_load(single_doc_text) or {}
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing YAML in {suite_file} or its configs: {e}"
            ) from e

        merged_config_data: Dict[str, Any] = {}
        for cp in config_paths:
            doc = _load_yaml_file(cp)
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


def clear_caches() -> None:
    """Clear discovery-level caches for deterministic fresh reads."""
    _read_text_cached.cache_clear()
    _load_yaml_file.cache_clear()
