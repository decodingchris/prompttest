from __future__ import annotations

from pathlib import Path

import pytest

from prompttest import llm


@pytest.mark.parametrize(
    "text, expected_pass, expected_reason",
    [
        ("EVALUATION: PASS - All good", True, "All good"),
        ("foo\nbar\nEVALUATION: PASS - Yay", True, "Yay"),
        ("EVALUATION: FAIL - Not correct", False, "Not correct"),
        ("foo\nEVALUATION: FAIL - Bad tone", False, "Bad tone"),
        ("", False, "Evaluation failed: LLM returned an empty response."),
        ("No verdict line here", False, "Invalid evaluation format."),
    ],
)
def test_parse_evaluation_variants(
    text: str, expected_pass: bool, expected_reason: str
):
    passed, reason = llm._parse_evaluation(text)
    assert passed is expected_pass
    assert expected_reason in reason


def test_cache_write_and_read_roundtrip(in_tmp_project: Path):
    key = llm._get_cache_key({"k": "v"})
    value = "cached-value"
    assert llm._read_cache(key) is None
    llm._write_cache(key, value)
    assert llm._read_cache(key) == value


@pytest.mark.asyncio
async def test_generate_uses_cache_and_sets_is_cached(
    in_tmp_project: Path, prime_generate_cache
):
    prompt = "Hello"
    model = "test-model"
    temp = 0.0
    prime_generate_cache(prompt, model, temp, "CACHED")
    llm.get_client.cache_clear()

    content, is_cached = await llm.generate(prompt, model, temp)
    assert content == "CACHED"
    assert is_cached is True


@pytest.mark.asyncio
async def test_evaluate_uses_cache_and_parses(
    in_tmp_project: Path, prime_evaluate_cache
):
    criteria = "X"
    model = "judge-model"
    temp = 0.0
    response = "ignored"
    prime_evaluate_cache(
        criteria, model, temp, response, {"passed": True, "reason": "Looks good"}
    )
    llm.get_client.cache_clear()

    passed, reason, is_cached = await llm.evaluate(response, criteria, model, temp)
    assert passed is True
    assert reason == "Looks good"
    assert is_cached is True
