from __future__ import annotations

import shutil

import pytest

from prompttest import llm


class _Msg:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Msg(content)


@pytest.fixture(autouse=True)
def clear_llm_caches():
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)
    yield
    llm.get_client.cache_clear()
    if llm.CACHE_DIR.exists():
        shutil.rmtree(llm.CACHE_DIR)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_cls, expected, is_auth_case",
    [
        pytest.param(
            type("MyAuth", (Exception,), {}),
            "Authentication failed. Please verify your OPENROUTER_API_KEY.",
            True,
            id="authentication-error",
        ),
        pytest.param(
            TimeoutError,
            "The request to the API timed out. Please try again.",
            False,
            id="timeout-error",
        ),
        pytest.param(
            RuntimeError,
            "Unexpected error while calling the API: boom",
            False,
            id="unexpected-error",
        ),
    ],
)
async def test_generate_error_paths(monkeypatch, exc_cls, expected, is_auth_case):
    class BadCompletions:
        async def create(self, *a, **k):
            raise exc_cls("boom")

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    if is_auth_case:
        monkeypatch.setattr(llm.openai, "AuthenticationError", exc_cls, raising=False)
    else:
        monkeypatch.setattr(
            llm.openai,
            "AuthenticationError",
            type("Auth", (Exception,), {}),
            raising=False,
        )
    monkeypatch.setattr(llm, "get_client", lambda: Client())

    with pytest.raises(llm.LLMError, match=expected):
        await llm.generate("p", "m", 0.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc_cls, expected, is_auth_case",
    [
        pytest.param(
            type("MyAuth", (Exception,), {}),
            "Authentication failed. Please verify your OPENROUTER_API_KEY.",
            True,
            id="authentication-error",
        ),
        pytest.param(
            TimeoutError,
            "The request to the API timed out. Please try again.",
            False,
            id="timeout-error",
        ),
        pytest.param(
            RuntimeError,
            "Unexpected error while calling the API: kaboom",
            False,
            id="unexpected-error",
        ),
    ],
)
async def test_evaluate_error_paths(monkeypatch, exc_cls, expected, is_auth_case):
    class BadCompletions:
        async def create(self, *a, **k):
            raise exc_cls("kaboom")

    class Client:
        def __init__(self):
            self.chat = type("X", (), {"completions": BadCompletions()})()

    if is_auth_case:
        monkeypatch.setattr(llm.openai, "AuthenticationError", exc_cls, raising=False)
    else:
        monkeypatch.setattr(
            llm.openai,
            "AuthenticationError",
            type("Auth", (Exception,), {}),
            raising=False,
        )
    monkeypatch.setattr(llm, "get_client", lambda: Client())

    with pytest.raises(llm.LLMError, match=expected):
        await llm.evaluate("resp", "criteria", "judge", 0.0)
