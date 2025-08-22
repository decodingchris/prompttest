from __future__ import annotations

from pathlib import Path

import pytest

from prompttest import runner
from prompttest.reporting import REPORTS_DIR


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_with_pass_and_fail_write_reports_and_summary(
    initialized_project: Path, mock_llm_selective, ensure_clean_cache_and_reports
):
    suite_path = Path("prompttests/demo.yml")
    suite_path.write_text(
        """
config:
  prompt: customer_service
tests:
  - id: will-pass
    inputs:
      user_name: "Alex"
      user_tier: "Premium"
      product_name: "Chrono-Watch"
      user_query: "Hi"
    criteria: "expect-pass - greet politely"
  - id: will-fail
    inputs:
      user_name: "Sam"
      user_tier: "Standard"
      product_name: "Chrono-Watch"
      user_query: "Refund now!"
    criteria: "expect-fail - be rude"
""",
        encoding="utf-8",
    )

    exit_code = await runner.run_all_tests()
    assert exit_code == 1

    assert REPORTS_DIR.exists()
    runs = [p for p in REPORTS_DIR.iterdir() if p.is_dir() and p.name != "latest"]
    assert runs, "No run directory created"
    run_dir = sorted(runs)[-1]

    f1 = run_dir / "demo-will-pass.md"
    f2 = run_dir / "demo-will-fail.md"
    assert f1.exists()
    assert f2.exists()

    content = f1.read_text(encoding="utf-8")
    assert "# ✅ Test Pass Report: `will-pass`" in content
    assert "- **Generation Model**:" in content
    assert "## Request (Prompt + Values)" in content


@pytest.mark.integration
@pytest.mark.asyncio
async def test_runner_handles_project_not_initialized_gracefully(
    in_tmp_project: Path, capsys
):
    code = await runner.run_all_tests()
    captured = capsys.readouterr().out
    assert code == 1
    assert "Error: Directory 'prompttests' not found." in captured
    assert "prompttest init" in captured


@pytest.mark.integration
@pytest.mark.asyncio
async def test_runner_handles_llm_error_and_shows_failure_panel(
    initialized_project: Path,
    ensure_clean_cache_and_reports,
    monkeypatch,
    capsys,
):
    Path("prompttests/one.yml").write_text(
        """
config:
  prompt: customer_service
tests:
  - id: only
    inputs: {}
    criteria: "anything"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod
    from prompttest.llm import LLMError

    async def gen_err(prompt: str, model: str, temperature: float):
        raise LLMError("API returned a 503 status code from provider 'foo'.")

    monkeypatch.setattr(llm_mod, "generate", gen_err)

    code = await runner.run_all_tests()
    out = capsys.readouterr().out
    assert code == 1
    assert "❌ FAIL: only" in out or "FAIL: only" in out
