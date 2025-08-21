from __future__ import annotations

import json
import shutil

import pytest

from prompttest import llm


@pytest.fixture(autouse=True)
def clean_cache():
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)
    yield
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)


@pytest.mark.asyncio
async def test_evaluate_structured_parse_happy_path(monkeypatch):
    verdict = llm._StructuredVerdict(passed=True, reason="Looks good")

    class Msg:
        def __init__(self):
            self.parsed = verdict

    class Resp:
        def __init__(self):
            self.choices = [type("Ch", (), {"message": Msg()})()]

    class Chat:
        async def parse(self, *a, **k):
            return Resp()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": Chat()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp", "criteria", "judge", 0.0)
    assert passed is True
    assert reason == "Looks good"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_structured_json_schema_fallback(monkeypatch):
    class BadParse:
        async def parse(self, *a, **k):
            raise RuntimeError("parse not available")

    class GoodCreate:
        async def create(self, *a, **k):
            return type(
                "Resp",
                (),
                {
                    "choices": [
                        type(
                            "Ch",
                            (),
                            {
                                "message": type(
                                    "M",
                                    (),
                                    {
                                        "content": json.dumps(
                                            {"passed": False, "reason": "Nope"}
                                        )
                                    },
                                )()
                            },
                        )()
                    ]
                },
            )()

    class Client:
        def __init__(self):
            self.chat = type(
                "X",
                (),
                {
                    "completions": type(
                        "C",
                        (),
                        {"parse": BadParse().parse, "create": GoodCreate().create},
                    )()
                },
            )()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp", "criteria", "judge", 0.7)
    assert passed is False
    assert reason == "Nope"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_structured_json_object_fallback(monkeypatch):
    class BadCompletions:
        async def parse(self, *a, **k):
            raise RuntimeError("parse failed")

        async def create(self, *a, **k):
            rf = k.get("response_format")
            if isinstance(rf, dict) and rf.get("type") == "json_schema":
                raise RuntimeError("json_schema also failed")
            return type(
                "Resp",
                (),
                {
                    "choices": [
                        type(
                            "Ch",
                            (),
                            {
                                "message": type(
                                    "M",
                                    (),
                                    {
                                        "content": json.dumps(
                                            {"passed": True, "reason": "Recovered"}
                                        )
                                    },
                                )()
                            },
                        )()
                    ]
                },
            )()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp", "criteria", "judge", 0.0)
    assert passed is True
    assert reason == "Recovered"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_all_structured_attempts_fail_then_text_mode(monkeypatch):
    class FailingCompletions:
        async def parse(self, *a, **k):
            raise RuntimeError("no parse")

        async def create(self, *a, **k):
            rf = k.get("response_format")
            msgs = k.get("messages") or []
            if rf is not None:
                raise RuntimeError("no schema path")
            if msgs and msgs[0].get("role") == "system":
                raise RuntimeError("no json_object path")
            return type(
                "Resp",
                (),
                {
                    "choices": [
                        type(
                            "Ch",
                            (),
                            {
                                "message": type(
                                    "M", (), {"content": "note\nEVALUATION: PASS - OK"}
                                )()
                            },
                        )()
                    ]
                },
            )()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": FailingCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp", "criteria", "judge", 0.2)
    assert passed is True
    assert reason == "OK"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_text_mode_cache_hit(monkeypatch):
    async def fake_try_structured_eval(**kwargs):
        return None, None, False

    monkeypatch.setattr(llm, "_try_structured_eval", fake_try_structured_eval)

    criteria = "C"
    response = "R"
    model = "M"
    temp = 0.0

    eval_prompt = llm._EVALUATION_PROMPT_TEMPLATE.format(
        criteria=criteria, response=response
    )
    key = llm._get_cache_key(
        {
            "v": 2,
            "mode": "text",
            "eval_prompt": eval_prompt,
            "model": model,
            "temperature": temp,
        }
    )
    llm._write_cache(key, "notes\nEVALUATION: PASS - From cache")

    monkeypatch.setattr(llm, "get_client", lambda: None)

    passed, reason, cached = await llm.evaluate(response, criteria, model, temp)
    assert passed is True
    assert reason == "From cache"
    assert cached is True
