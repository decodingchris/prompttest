from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Tuple, cast

import openai
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

CACHE_DIR = Path(".prompttest_cache")

_OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/decodingchris/prompttest",
    "X-Title": "prompttest",
}


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


_EVALUATION_PROMPT_TEMPLATE = """
You are an expert evaluator. Determine if the response adheres to the criteria.

Criteria:
{criteria}

Response:
{response}

Instructions:
- Provide brief analysis if needed.
- Your final verdict must be the LAST line, in this exact format (no quotes, no backticks, no code blocks):
EVALUATION: PASS - <brief, one-sentence justification>
or
EVALUATION: FAIL - <brief, one-sentence justification>
""".strip()


class _StructuredVerdict(BaseModel):
    passed: bool | None = None
    reason: str


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
        default_headers=_OPENROUTER_HEADERS,
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
    except getattr(openai, "AuthenticationError", Exception) as e:
        raise LLMError(
            "Authentication failed. Please verify your OPENROUTER_API_KEY."
        ) from e
    except TimeoutError as e:
        raise LLMError("The request to the API timed out. Please try again.") from e
    except Exception as e:
        raise LLMError(f"Unexpected error while calling the API: {e}") from e


_STRUCTURED_HINT = (
    "Return only a JSON object with fields:\n"
    "  passed: boolean\n"
    "  reason: short string justification\n"
    "No extra text."
)


async def _try_structured_eval(
    *,
    criteria: str,
    response: str,
    model: str,
    temperature: float,
) -> tuple[bool | None, str | None, bool]:
    prompt = (
        "Criteria:\n"
        f"{criteria}\n\n"
        "Response:\n"
        f"{response}\n\n"
        "Decide if the response meets the criteria."
    )

    cache_key = _get_cache_key(
        {
            "v": 2,
            "mode": "structured",
            "eval_prompt": prompt,
            "model": model,
            "temperature": temperature,
        }
    )
    cached = _read_cache(cache_key)
    if cached:
        try:
            v_cached = _StructuredVerdict.model_validate_json(cached)
            return v_cached.passed, v_cached.reason.strip(), True
        except Exception:
            pass

    client = get_client()

    # 1) Native Pydantic parsing
    try:
        parsed_resp = await client.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=_StructuredVerdict,
            temperature=temperature,
        )
        msg = parsed_resp.choices[0].message
        v_parsed = cast(Optional[_StructuredVerdict], getattr(msg, "parsed", None))
        if v_parsed is not None:
            _write_cache(cache_key, v_parsed.model_dump_json())
            return v_parsed.passed, v_parsed.reason.strip(), False
    except Exception:
        pass

    # 2) JSON Schema constrained outputs
    try:
        rf = {
            "type": "json_schema",
            "json_schema": {
                "name": "_StructuredVerdict",
                "schema": _StructuredVerdict.model_json_schema(),
                "strict": True,
            },
        }
        schema_resp = await client.chat.completions.create(
            model=model,
            messages=cast(Any, [{"role": "user", "content": prompt}]),
            response_format=cast(Any, rf),
            temperature=0.0,
        )
        content = (schema_resp.choices[0].message.content or "").strip()
        try:
            v_schema = _StructuredVerdict.model_validate_json(content)
        except ValidationError:
            v_schema = _StructuredVerdict.model_validate(json.loads(content))
        _write_cache(cache_key, v_schema.model_dump_json())
        return v_schema.passed, v_schema.reason.strip(), False
    except Exception:
        pass

    # 3) JSON mode
    try:
        json_resp = await client.chat.completions.create(
            model=model,
            messages=cast(
                Any,
                [
                    {"role": "system", "content": _STRUCTURED_HINT},
                    {"role": "user", "content": prompt},
                ],
            ),
            response_format=cast(Any, {"type": "json_object"}),
            temperature=0.0,
        )
        content = (json_resp.choices[0].message.content or "").strip()
        try:
            v_json = _StructuredVerdict.model_validate_json(content)
        except ValidationError:
            v_json = _StructuredVerdict.model_validate(json.loads(content))
        _write_cache(cache_key, v_json.model_dump_json())
        return v_json.passed, v_json.reason.strip(), False
    except Exception:
        pass

    return None, None, False


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

    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not ln.startswith("```") and not ln.endswith("```")]

    for line in reversed(lines):
        if line.startswith("`") and line.endswith("`") and len(line) >= 2:
            line = line[1:-1].strip()
        m = re.match(r"(?i)^\s*EVALUATION:\s*(PASS|FAIL)\s*-\s*(.+)$", line)
        if m:
            kind, reason = m.groups()
            return (kind.upper() == "PASS"), reason.strip()
    return False, f"Invalid evaluation format. Full text: {text}"


async def evaluate(
    response: str, criteria: str, model: str, temperature: float
) -> Tuple[bool, str, bool]:
    s_passed, s_reason, s_cached = await _try_structured_eval(
        criteria=criteria, response=response, model=model, temperature=temperature
    )
    if s_passed is not None and s_reason is not None:
        return bool(s_passed), s_reason, s_cached

    eval_prompt = _EVALUATION_PROMPT_TEMPLATE.format(
        criteria=criteria, response=response
    )
    cache_key = _get_cache_key(
        {
            "v": 2,
            "mode": "text",
            "eval_prompt": eval_prompt,
            "model": model,
            "temperature": temperature,
        }
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
