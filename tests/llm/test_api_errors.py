from __future__ import annotations

import shutil
from typing import Any

import pytest

from prompttest import llm


class _Msg:
    def __init__(self, content: Any):
        self.content = content


class _Choice:
    def __init__(self, content: Any):
        self.message = _Msg(content)


class _Completions:
    def __init__(self, content: Any = "OK"):
        self._content = content

    async def create(self, model: str, messages: list[dict], temperature: float):
        return type("Resp", (), {"choices": [_Choice(self._content)]})()


class _Chat:
    def __init__(self, content: Any = "OK"):
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: Any = "OK"):
        self.chat = _Chat(content)


@pytest.fixture(autouse=True)
def clear_caches(tmp_path):
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)
    yield
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)


def test_get_client_raises_without_env(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="OPENROUTER_API_KEY not found"):
        llm.get_client()


def test_get_client_succeeds_with_env(monkeypatch):
    class FakeOpenAI:
        def __init__(self, base_url: str, api_key: str, **kwargs: Any):
            assert api_key == "k"
            self.chat = _Chat("HELLO")

    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm.openai, "AsyncOpenAI", FakeOpenAI)

    c1 = llm.get_client()
    assert hasattr(c1, "chat")
    assert llm.get_client() is c1


@pytest.mark.asyncio
async def test_generate_happy_path(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: _Client("GEN-CONTENT-A"))
    content, cached = await llm.generate("p-A", "m-A", 0.1)
    assert content == "GEN-CONTENT-A"
    assert cached is False


@pytest.mark.asyncio
async def test_generate_handles_none_content(monkeypatch):
    monkeypatch.setattr(llm, "get_client", lambda: _Client(None))
    content, cached = await llm.generate("p-B", "m-B", 0.2)
    assert content == ""
    assert cached is False


@pytest.mark.asyncio
async def test_generate_api_status_error_with_provider(monkeypatch):
    class MyAPIStatusError(Exception):
        def __init__(self):
            self.status_code = 503
            self.body = {"error": {"metadata": {"provider_name": "foo"}}}

    monkeypatch.setattr(llm.openai, "APIStatusError", MyAPIStatusError)

    class BadCompletions:
        async def create(self, *a, **k):
            raise MyAPIStatusError()

    class BadClient:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: BadClient())
    with pytest.raises(
        llm.LLMError, match="API returned a 503 status code from provider 'foo'"
    ):
        await llm.generate("p-C", "m-C", 0.3)


@pytest.mark.asyncio
async def test_generate_api_status_error_without_dict_body(monkeypatch):
    class MyAPIStatusError(Exception):
        def __init__(self):
            self.status_code = 500
            self.body = "oops"

    monkeypatch.setattr(llm.openai, "APIStatusError", MyAPIStatusError)

    class BadCompletions:
        async def create(self, *a, **k):
            raise MyAPIStatusError()

    class BadClient:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: BadClient())
    with pytest.raises(llm.LLMError, match="API returned a non-200 status code: 500."):
        await llm.generate("p-D", "m-D", 0.4)


@pytest.mark.asyncio
async def test_generate_api_connection_error(monkeypatch):
    class MyAPIConnectionError(Exception):
        def __init__(self):
            self.__cause__ = OSError("network down")

    monkeypatch.setattr(llm.openai, "APIConnectionError", MyAPIConnectionError)

    class BadCompletions:
        async def create(self, *a, **k):
            raise MyAPIConnectionError()

    class BadClient:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: BadClient())
    with pytest.raises(
        llm.LLMError,
        match="Could not connect to the API. Please check your network connection.",
    ):
        await llm.generate("p-E", "m-E", 0.5)


@pytest.mark.asyncio
async def test_evaluate_happy_path(monkeypatch):
    class EvalCompletions:
        async def create(self, *a, **k):
            return type(
                "Resp",
                (),
                {"choices": [_Choice("Some notes\nEVALUATION: PASS - Meets spec")]},
            )()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": EvalCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp-1", "criteria-1", "judge-1", 0.0)
    assert passed is True
    assert reason == "Meets spec"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_parses_fail(monkeypatch):
    class EvalCompletions:
        async def create(self, *a, **k):
            return type(
                "Resp",
                (),
                {"choices": [_Choice("notes\nEVALUATION: FAIL - Not sufficient")]},
            )()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": EvalCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("r", "c", "m", 0.0)
    assert passed is False
    assert reason == "Not sufficient"
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_invalid_format(monkeypatch):
    class EvalCompletions:
        async def create(self, *a, **k):
            return type("Resp", (), {"choices": [_Choice("No verdict present")]})()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": EvalCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp-2", "criteria-2", "judge-2", 0.0)
    assert passed is False
    assert reason.startswith("Invalid evaluation format")
    assert cached is False


@pytest.mark.asyncio
async def test_evaluate_api_status_error(monkeypatch):
    class MyAPIStatusError(Exception):
        def __init__(self):
            self.status_code = 429
            self.body = {"error": {"metadata": {"provider_name": "bar"}}}

    monkeypatch.setattr(llm.openai, "APIStatusError", MyAPIStatusError)

    class BadCompletions:
        async def create(self, *a, **k):
            raise MyAPIStatusError()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    with pytest.raises(
        llm.LLMError, match="API returned a 429 status code from provider 'bar'"
    ):
        await llm.evaluate("resp-3", "criteria-3", "judge-3", 0.0)


@pytest.mark.asyncio
async def test_evaluate_handles_none_content(monkeypatch):
    class EvalCompletions:
        async def create(self, *a, **k):
            return type("Resp", (), {"choices": [_Choice(None)]})()

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": EvalCompletions()})()

    monkeypatch.setattr(llm, "get_client", lambda: Client())
    passed, reason, cached = await llm.evaluate("resp-4", "criteria-4", "judge-4", 0.0)
    assert passed is False
    assert reason == "Evaluation failed: LLM returned an empty response."
    assert cached is False
