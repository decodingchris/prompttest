from __future__ import annotations

from pathlib import Path

from prompttest.discovery import PROMPTS_DIR
from prompttest.models import (
    Config,
    TestCase as PTTestCase,
    TestResult as PTTestResult,
)
from prompttest.reporting import (
    create_run_directory,
    write_report_file,
)


def test_write_single_report_file(in_tmp_project: Path):
    (PROMPTS_DIR).mkdir(exist_ok=True)
    prompt_name = "customer_service"
    prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
    prompt_path.write_text("Prompt body here", encoding="utf-8")

    tr = PTTestResult(
        test_case=PTTestCase(id="t-1", inputs={}, criteria="crit"),
        suite_path=Path("prompttests/suite.yml"),
        config=Config(
            generation_model="g-model",
            evaluation_model="e-model",
            generation_temperature=0.1,
            evaluation_temperature=0.0,
        ),
        prompt_name=prompt_name,
        rendered_prompt="Rendered prompt",
        passed=True,
        response="Resp",
        evaluation="OK",
    )
    run_dir = create_run_directory()
    write_report_file(tr, run_dir)
    report_path = run_dir / "suite-t-1.md"
    content = report_path.read_text(encoding="utf-8")
    assert "# ✅ Test Pass Report: `t-1`" in content
    assert "- **Generation Model**: `g-model`" in content
    assert "## Request (Prompt + Values)" in content
