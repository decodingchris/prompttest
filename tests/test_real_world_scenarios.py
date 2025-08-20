from __future__ import annotations

import asyncio
from pathlib import Path

from prompttest import runner
from prompttest.discovery import PROMPTS_DIR


def write_prompt():
    PROMPTS_DIR.mkdir(exist_ok=True)
    (PROMPTS_DIR / "cs.txt").write_text(
        """
---[SYSTEM]---
You are an expert support agent.
---[USER]---
Tier: {tier}
Question: {q}
""",
        encoding="utf-8",
    )


def test_scraped_from_wild_html_entities_and_unicode(monkeypatch, in_tmp_project: Path):
    write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/test1.yml").write_text(
        """
config:
  prompt: cs
  generation_model: "test/gen"
  evaluation_model: "test/eval"
tests:
  - id: wild
    inputs:
      tier: "Standard"
      q: "Price shows as &euro; 49.99 — why?"
    criteria: "expect-pass"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "The price is € 49.99, thanks for asking.", False

    async def fake_eval(response: str, criteria: str, model: str, temperature: float):
        ok = "€" in response
        return ok, "Entity normalized", False

    monkeypatch.setattr(llm_mod, "generate", fake_gen)
    monkeypatch.setattr(llm_mod, "evaluate", fake_eval)

    code = asyncio.run(runner.run_all_tests())
    assert code == 0


def test_generated_by_tool_almost_correct(monkeypatch, in_tmp_project: Path):
    write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/test2.yml").write_text(
        """
config:
  prompt: cs
  generation_model: "test/gen"
  evaluation_model: "test/eval"
tests:
  - id: tool
    inputs:
      tier: "Premium"
      q: "My tracking number is ABC-123"
    criteria: "expect-pass"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "Tracking ABC-123 is in transit.", False

    async def fake_eval(response: str, criteria: str, model: str, temperature: float):
        return (
            ("ABC-123" in response and "in transit" in response),
            "Recognized tracking",
            False,
        )

    monkeypatch.setattr(llm_mod, "generate", fake_gen)
    monkeypatch.setattr(llm_mod, "evaluate", fake_eval)

    code = asyncio.run(runner.run_all_tests())
    assert code == 0


def test_human_edited_broke_format(monkeypatch, in_tmp_project: Path):
    write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/test3.yml").write_text(
        """
config:
  prompt: cs
  generation_model: "test/gen"
  evaluation_model: "test/eval"
tests:
  - id: human-edited
    inputs:
      tier: "Standard"
      q: "I NEED HELP!!!"
    criteria: "expect-fail"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "CALM DOWN. Read the manual.", False

    async def fake_eval(response: str, criteria: str, model: str, temperature: float):
        return ("CALM DOWN" not in response), "Tone too harsh", False

    monkeypatch.setattr(llm_mod, "generate", fake_gen)
    monkeypatch.setattr(llm_mod, "evaluate", fake_eval)

    code = asyncio.run(runner.run_all_tests())
    assert code == 1


def test_legacy_system_old_format(monkeypatch, in_tmp_project: Path):
    write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/test4.yml").write_text(
        """
config:
  prompt: cs
  generation_model: "test/gen"
  evaluation_model: "test/eval"
tests:
  - id: legacy
    inputs:
      tier: "Legacy-VIP"
      q: "Return policy?"
    criteria: "expect-pass"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "As a VIP, you have 30 days to return items.", False

    async def fake_eval(response: str, criteria: str, model: str, temperature: float):
        return ("30 days" in response), "Policy correct", False

    monkeypatch.setattr(llm_mod, "generate", fake_gen)
    monkeypatch.setattr(llm_mod, "evaluate", fake_eval)

    code = asyncio.run(runner.run_all_tests())
    assert code == 0


def test_corrupted_in_transit_partial_data(monkeypatch, in_tmp_project: Path):
    write_prompt()
    Path("prompttests").mkdir()
    Path("prompttests/test5.yml").write_text(
        """
config:
  prompt: cs
  generation_model: "test/gen"
  evaluation_model: "test/eval"
tests:
  - id: corrupt
    inputs:
      tier: ""
      q: "My parcel ????"
    criteria: "expect-fail"
""",
        encoding="utf-8",
    )

    from prompttest import llm as llm_mod

    async def fake_gen(prompt: str, model: str, temperature: float):
        return "", False

    async def fake_eval(response: str, criteria: str, model: str, temperature: float):
        return (bool(response.strip())), "Empty response", False

    monkeypatch.setattr(llm_mod, "generate", fake_gen)
    monkeypatch.setattr(llm_mod, "evaluate", fake_eval)

    code = asyncio.run(runner.run_all_tests())
    assert code == 1
