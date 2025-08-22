from __future__ import annotations

from prompttest import llm


def test_parse_evaluation_ignores_code_fences_and_backticks():
    text = """
```json
{"foo": "bar"}
```
`EVALUATION: FAIL - Reason in backticks`
"""
    passed, reason = llm._parse_evaluation(text)
    assert passed is False
    assert reason == "Reason in backticks"
