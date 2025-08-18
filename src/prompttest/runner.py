# src/prompttest/runner.py
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai
import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

from .models import Config, TestCase, TestResult, TestSuite

# --- Constants ---

PROMPTTESTS_DIR = Path("prompttests")
PROMPTS_DIR = Path("prompts")
CACHE_DIR = Path(".prompttest_cache")

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


# --- LLM Client ---


@lru_cache(maxsize=1)
def get_llm_client() -> openai.AsyncOpenAI:
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


# --- Caching ---


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
    cache_file.write_text(value, "utf-8")


# --- Core Execution Logic ---


async def _generate(prompt: str, model: str, temperature: float) -> Tuple[str, bool]:
    cache_key = _get_cache_key(
        {"prompt": prompt, "model": model, "temperature": temperature}
    )
    cached = _read_cache(cache_key)
    if cached:
        return cached, True

    client = get_llm_client()
    chat_completion = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    content = chat_completion.choices[0].message.content or ""
    _write_cache(cache_key, content)
    return content, False


def _parse_evaluation(text: str) -> Tuple[bool, str]:
    last_line = text.strip().splitlines()[-1]
    if "EVALUATION: PASS" in last_line:
        return True, last_line.replace("EVALUATION: PASS -", "").strip()
    if "EVALUATION: FAIL" in last_line:
        return False, last_line.replace("EVALUATION: FAIL -", "").strip()
    return False, f"Invalid evaluation format. Full text: {text}"


async def _evaluate(response: str, criteria: str, model: str) -> Tuple[bool, str, bool]:
    eval_prompt = _EVALUATION_PROMPT_TEMPLATE.format(
        criteria=criteria, response=response
    )
    cache_key = _get_cache_key(
        {"eval_prompt": eval_prompt, "model": model, "temperature": 0.0}
    )
    cached = _read_cache(cache_key)
    if cached:
        passed, reason = _parse_evaluation(cached)
        return passed, reason, True

    client = get_llm_client()
    chat_completion = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": eval_prompt}],
        temperature=0.0,
    )
    content = chat_completion.choices[0].message.content or ""
    _write_cache(cache_key, content)
    passed, reason = _parse_evaluation(content)
    return passed, reason, False


def _format_prompt(template: str, inputs: Dict[str, Any]) -> str:
    filled_template = template
    for key, value in inputs.items():
        filled_template = filled_template.replace(f"{{{key}}}", str(value))
    return filled_template


async def _run_test_case(
    suite: TestSuite, test_case: TestCase, progress: Progress, task_id: TaskID
) -> TestResult:
    try:
        prompt_str = _format_prompt(suite.prompt_content, test_case.inputs)
        model = suite.config.generation_model
        if not model:
            raise ValueError("`generation_model` is not defined.")

        response, gen_cached = await _generate(
            prompt_str, model, suite.config.temperature
        )
        progress.update(task_id, advance=0.5)

        eval_model = suite.config.evaluation_model
        if not eval_model:
            raise ValueError("`evaluation_model` is not defined.")
        passed, reason, eval_cached = await _evaluate(
            response, test_case.criteria, eval_model
        )
        progress.update(task_id, advance=0.5)

        return TestResult(
            test_case=test_case,
            suite_path=suite.file_path,
            passed=passed,
            response=response,
            evaluation=reason,
            is_cached=gen_cached and eval_cached,
        )
    except Exception as e:
        progress.update(task_id, advance=1)
        return TestResult(
            test_case=test_case,
            suite_path=suite.file_path,
            passed=False,
            response="",
            evaluation="",
            error=str(e),
        )


# --- Configuration & Discovery ---


def _deep_merge(source: dict, destination: dict) -> dict:
    """Recursively merge dictionaries, with values from 'source' overwriting 'destination'."""
    for key, value in source.items():
        if (
            isinstance(value, dict)
            and key in destination
            and isinstance(destination[key], dict)
        ):
            destination[key] = _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


def _get_config_file_paths(start_path: Path) -> List[Path]:
    """Finds all prompttest.yml files from the start_path up to the root."""
    paths_to_check = []
    current_dir = start_path.parent
    stop_dir = PROMPTTESTS_DIR.resolve().parent

    while current_dir != stop_dir and PROMPTTESTS_DIR.name in str(current_dir):
        config_path = current_dir / "prompttest.yml"
        if config_path.is_file():
            paths_to_check.append(config_path)
        current_dir = current_dir.parent
    return list(reversed(paths_to_check))


def _discover_and_prepare_suites() -> List[TestSuite]:
    if not PROMPTTESTS_DIR.is_dir():
        raise FileNotFoundError(f"Directory '{PROMPTTESTS_DIR}' not found.")

    suites = []
    suite_files = list(PROMPTTESTS_DIR.rglob("*.yml")) + list(
        PROMPTTESTS_DIR.rglob("*.yaml")
    )

    for suite_file in suite_files:
        if suite_file.name == "prompttest.yml":
            continue

        config_paths = _get_config_file_paths(suite_file)
        all_files_for_parsing = config_paths + [suite_file]

        merged_config_data: Dict[str, Any] = {}
        for path in all_files_for_parsing:
            try:
                data = (
                    yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.FullLoader)
                    or {}
                )
                if "config" in data:
                    merged_config_data = _deep_merge(data["config"], merged_config_data)
            except yaml.YAMLError:
                pass

        suite_config = Config(**merged_config_data)

        full_yaml_text = "\n".join(
            p.read_text(encoding="utf-8") for p in all_files_for_parsing
        )
        try:
            parsed_data = yaml.load(full_yaml_text, Loader=yaml.FullLoader) or {}
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing YAML in {suite_file} or its configs: {e}"
            ) from e

        prompt_name = merged_config_data.get("prompt") or parsed_data.get(
            "config", {}
        ).get("prompt")
        if not prompt_name:
            raise ValueError(f"Suite '{suite_file}' is missing a `prompt` definition.")

        prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        prompt_content = prompt_path.read_text(encoding="utf-8")
        test_cases = [TestCase(**test) for test in parsed_data.get("tests", [])]

        if test_cases:
            suites.append(
                TestSuite(
                    file_path=suite_file,
                    config=suite_config,
                    tests=test_cases,
                    prompt_name=prompt_name,
                    prompt_content=prompt_content,
                )
            )
    return suites


# --- UI & Reporting ---


def _render_failures(console: Console, results: List[TestResult]) -> None:
    """Renders a detailed panel for each failed test."""
    failures = [r for r in results if not r.passed]
    if not failures:
        return

    for result in failures:
        failure_title = f"[bold red]❌ {result.test_case.id}[/bold red]"
        content: Any
        if result.error:
            content = Text(result.error, style="default")
        else:
            details_table = Table.grid(padding=(1, 2))
            details_table.add_column(style="bold blue", no_wrap=True)
            details_table.add_column()
            details_table.add_row("Criteria:", Text(result.test_case.criteria.strip()))
            details_table.add_row("Response:", Text(result.response.strip()))
            details_table.add_row("Evaluation:", Text(result.evaluation.strip()))
            content = details_table

        console.print(
            Panel(
                content,
                title=failure_title,
                border_style="red",
                expand=False,
                padding=(1, 2),
            )
        )


def _render_suite_header(console: Console, suite: TestSuite) -> None:
    """Renders the panel with test suite configuration details."""
    header_table = Table.grid(padding=(1, 2))
    header_table.add_column(style="bold blue")
    header_table.add_column()

    test_file_path = suite.file_path
    prompt_file_path = PROMPTS_DIR / f"{suite.prompt_name}.txt"

    header_table.add_row("Test File:", f"[cyan]{test_file_path}[/cyan]")
    header_table.add_row("Prompt File:", f"[cyan]{prompt_file_path}[/cyan]")
    header_table.add_row("Generation Model:", suite.config.generation_model or "N/A")
    header_table.add_row("Evaluation Model:", suite.config.evaluation_model or "N/A")

    console.print(Panel(header_table, title="Test Info", expand=False, padding=(1, 2)))
    console.print()


def _render_suite_results(console: Console, suite_results: List[TestResult]) -> None:
    """Renders the panel with the pass/fail results for a suite."""
    result_lines = []
    for result in suite_results:
        cached_tag = " [dim](cached)[/dim]" if result.is_cached else ""
        if result.passed:
            result_lines.append(
                f"[green]✅ PASS: {result.test_case.id}[/green]{cached_tag}"
            )
        else:
            result_lines.append(
                f"[red]❌ FAIL: {result.test_case.id}[/red]{cached_tag}"
            )

    results_markup = "\n\n".join(result_lines)
    results_text = Text.from_markup(results_markup)

    console.print(
        Panel(results_text, title="Test Results", expand=False, padding=(1, 2))
    )
    console.print()


# --- Main Orchestrator ---


async def run_all_tests() -> int:
    console = Console()
    start_time = time.perf_counter()
    try:
        suites = _discover_and_prepare_suites()
    except (FileNotFoundError, ValueError, EnvironmentError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    except Exception:
        console.print_exception(show_locals=True)
        return 1

    if not suites:
        console.print("[yellow]No tests found.[/yellow]")
        return 0

    total_tests = sum(len(s.tests) for s in suites)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )

    with Live(progress, console=console, vertical_overflow="visible", transient=True):
        all_results: List[TestResult] = []
        overall_task = progress.add_task("[bold]Running tests", total=total_tests)

        for suite in suites:
            tasks = [
                _run_test_case(suite, tc, progress, overall_task) for tc in suite.tests
            ]
            suite_results = await asyncio.gather(*tasks)
            all_results.extend(suite_results)

    console.print()

    results_by_suite = defaultdict(list)
    for r in all_results:
        results_by_suite[r.suite_path].append(r)

    for i, suite in enumerate(suites):
        suite_results = results_by_suite[suite.file_path]
        _render_suite_header(console, suite)
        _render_suite_results(console, suite_results)
        if i < len(suites) - 1:
            console.print()

    elapsed_time = time.perf_counter() - start_time
    passed_count = sum(1 for r in all_results if r.passed)
    failed_count = total_tests - passed_count

    _render_failures(console, all_results)

    summary_text = Text.from_markup(
        f"[bold red]{failed_count} failed[/bold red], [bold green]{passed_count} passed[/bold green] in {elapsed_time:.2f}s"
    )
    console.print()
    console.print(
        Panel(
            summary_text,
            style="default",
            title="Test Summary",
            expand=False,
            padding=(1, 2),
        )
    )
    console.print()

    return 1 if failed_count > 0 else 0
