# src/prompttest/llm.py
from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Tuple

import openai
from dotenv import load_dotenv

CACHE_DIR = Path(".prompttest_cache")


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


_EVALUATION_PROMPT_TEMPLATE = """
You are an expert evaluator. Your task is to determine if the following AI-generated response strictly adheres to the given criteria.

**Criteria:**
{criteria}

**Response to Evaluate:**
{response}

Analyze the response against the criteria.
Your final verdict must be on the last line, in the format:
`EVALUATION: (PASS|FAIL) - <brief, one-sentence justification>`
For example: `EVALUATION: PASS - The response correctly identified the user's premium status.`
Another example: `EVALUATION: FAIL - The response was defensive and did not adopt an empathetic tone.`
""".strip()


@lru_cache(maxsize=1)
def get_client() -> openai.AsyncOpenAI:
    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not found. Please add it to your .env file."
        )

    return openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def _get_cache_key(data: Any) -> str:
    serialized_data = json.dumps(data, sort_keys=True).encode("utf-8")
    return hashlib.sha256(serialized_data).hexdigest()


def _read_cache(key: str) -> Optional[str]:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / key
    if cache_file.exists():
        return cache_file.read_text("utf-8")
    return None


def _write_cache(key: str, value: str) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / key
    tmp_file = CACHE_DIR / f".{key}.tmp"
    tmp_file.write_text(value, "utf-8")
    tmp_file.replace(cache_file)


async def _chat_completions_create(
    *,
    model: str,
    messages: Any,
    temperature: float,
):
    """
    Centralized wrapper for client.chat.completions.create with consistent error translation.
    'messages' is typed as Any to satisfy the OpenAI SDK's broad union of message param types.
    """
    client = get_client()
    try:
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
    except openai.APIStatusError as e:
        status = getattr(e, "status_code", None)
        message = f"API returned a non-200 status code: {status}."
        body = getattr(e, "body", None)
        if isinstance(body, dict):
            provider = body.get("error", {}).get("metadata", {}).get("provider_name")
            provider_msg = f" from provider '{provider}'" if provider else ""
            message = f"API returned a {status} status code{provider_msg}. The service may be temporarily unavailable."
        raise LLMError(message) from e
    except openai.APIConnectionError as e:
        raise LLMError(
            f"Could not connect to the API. Please check your network connection. Details: {getattr(e, '__cause__', None)}"
        ) from e


async def generate(prompt: str, model: str, temperature: float) -> Tuple[str, bool]:
    cache_key = _get_cache_key(
        {"prompt": prompt, "model": model, "temperature": temperature}
    )
    cached = _read_cache(cache_key)
    if cached:
        return cached, True

    chat_completion = await _chat_completions_create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )

    content = ""
    if (
        chat_completion.choices
        and chat_completion.choices[0].message
        and chat_completion.choices[0].message.content is not None
    ):
        content = chat_completion.choices[0].message.content

    _write_cache(cache_key, content)
    return content, False


def _parse_evaluation(text: str) -> Tuple[bool, str]:
    s = text.strip()
    if not s:
        return False, "Evaluation failed: LLM returned an empty response."

    for line in reversed(s.splitlines()):
        m = re.match(r"\s*EVALUATION:\s*(PASS|FAIL)\s*-\s*(.*)$", line, flags=re.I)
        if m:
            kind, reason = m.groups()
            return (kind.upper() == "PASS"), reason.strip()
    return False, f"Invalid evaluation format. Full text: {text}"


async def evaluate(
    response: str, criteria: str, model: str, temperature: float
) -> Tuple[bool, str, bool]:
    eval_prompt = _EVALUATION_PROMPT_TEMPLATE.format(
        criteria=criteria, response=response
    )
    cache_key = _get_cache_key(
        {"eval_prompt": eval_prompt, "model": model, "temperature": temperature}
    )
    cached = _read_cache(cache_key)
    if cached:
        passed, reason = _parse_evaluation(cached)
        return passed, reason, True

    chat_completion = await _chat_completions_create(
        model=model,
        messages=[{"role": "user", "content": eval_prompt}],
        temperature=temperature,
    )

    content = ""
    if (
        chat_completion.choices
        and chat_completion.choices[0].message
        and chat_completion.choices[0].message.content is not None
    ):
        content = chat_completion.choices[0].message.content

    _write_cache(cache_key, content)
    passed, reason = _parse_evaluation(content)
    return passed, reason, False
