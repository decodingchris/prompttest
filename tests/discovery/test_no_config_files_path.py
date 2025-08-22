from __future__ import annotations

from pathlib import Path

from prompttest.discovery import PROMPTS_DIR, discover_and_prepare_suites


def test_discover_with_no_config_files_uses_empty_anchors_prelude(
    in_tmp_project: Path,
):
    PROMPTS_DIR.mkdir(exist_ok=True)
    (PROMPTS_DIR / "cs.txt").write_text("Body", encoding="utf-8")

    pdir = in_tmp_project / "prompttests"
    pdir.mkdir()
    (pdir / "suite.yml").write_text(
        "config:\n  prompt: cs\ntests:\n  - id: t\n    inputs: {}\n    criteria: 'ok'\n",
        encoding="utf-8",
    )

    suites = discover_and_prepare_suites()
    assert len(suites) == 1
    s = suites[0]
    assert s.file_path == Path("prompttests/suite.yml")
    assert s.prompt_name == "cs"
    assert s.tests[0].id == "t"
