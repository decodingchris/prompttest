# src/prompttest/runner.py
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from collections import defaultdict
from datetime import datetime
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
REPORTS_DIR = Path(".prompttest_reports")
MAX_FAILURE_LINES = 3

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

    content = ""
    if (
        chat_completion.choices
        and chat_completion.choices[0].message
        and chat_completion.choices[0].message.content is not None
    ):
        content = chat_completion.choices[0].message.content
    else:
        # Handle cases where the API returns an empty or malformed response
        # by treating the response as an empty string.
        pass

    _write_cache(cache_key, content)
    return content, False


def _parse_evaluation(text: str) -> Tuple[bool, str]:
    if not text.strip():
        return False, "Evaluation failed: LLM returned an empty response."

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

    content = ""
    if (
        chat_completion.choices
        and chat_completion.choices[0].message
        and chat_completion.choices[0].message.content is not None
    ):
        content = chat_completion.choices[0].message.content
    else:
        # Handle cases where the API returns an empty or malformed response
        # by treating the evaluation as an empty string.
        pass

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
    prompt_str = ""
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
            config=suite.config,
            prompt_name=suite.prompt_name,
            rendered_prompt=prompt_str,
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
            config=suite.config,
            prompt_name=suite.prompt_name,
            rendered_prompt=prompt_str,
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

        # 1. Prepare a single YAML document with all anchors available up front.
        def _indent_block(s: str, spaces: int = 2) -> str:
            pad = " " * spaces
            return "\n".join((pad + line if line else line) for line in s.splitlines())

        if config_paths:
            # Inject config files under a dummy key to make their anchors available
            anchors_prelude = "__anchors__:\n" + "\n".join(
                _indent_block(p.read_text(encoding="utf-8")) for p in config_paths
            )
        else:
            anchors_prelude = "__anchors__: {}\n"

        single_doc_text = (
            anchors_prelude + "\n" + suite_file.read_text(encoding="utf-8")
        )

        try:
            # Use FullLoader to ensure anchors/aliases are processed
            parsed_single: Dict[str, Any] = (
                yaml.load(single_doc_text, Loader=yaml.FullLoader) or {}
            )
        except yaml.YAMLError as e:
            raise ValueError(
                f"Error parsing YAML in {suite_file} or its configs: {e}"
            ) from e

        # 2. Merge configs with hierarchy (global -> local suite) for override behavior.
        merged_config_data: Dict[str, Any] = {}
        for cp in config_paths:
            doc = (
                yaml.load(cp.read_text(encoding="utf-8"), Loader=yaml.FullLoader) or {}
            )
            merged_config_data = _deep_merge(doc.get("config", {}), merged_config_data)

        # The suite file's config overrides the global configs
        merged_config_data = _deep_merge(
            parsed_single.get("config", {}) or {}, merged_config_data
        )
        suite_config = Config(**merged_config_data)

        prompt_name = merged_config_data.get("prompt")
        if not prompt_name:
            raise ValueError(f"Suite '{suite_file}' is missing a `prompt` definition.")

        prompt_path = PROMPTS_DIR / f"{prompt_name}.txt"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        prompt_content = prompt_path.read_text(encoding="utf-8")

        # 3. Tests are taken from the single parsed doc where aliases were resolved.
        test_cases = [TestCase(**t) for t in (parsed_single.get("tests") or [])]

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


def _truncate_text(text: str, max_lines: int) -> str:
    """Truncates text to a maximum number of lines, adding '[...]' if truncated."""
    lines = text.strip().splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n[...]"
    return text


def _md_rel_path(target: Path, start: Path) -> str:
    """Return a Markdown-friendly relative path (POSIX-style slashes)."""
    rel = os.path.relpath(target.resolve(), start.resolve())
    return rel.replace(os.sep, "/")


def _write_report_file(result: TestResult, run_dir: Path) -> None:
    """Writes a detailed .md file for a single test result."""
    suite_name = result.suite_path.stem
    test_id = result.test_case.id
    filename = f"{suite_name}-{test_id}.md"
    report_path = run_dir / filename

    status_emoji = "✅" if result.passed else "❌"
    status_text = "Pass" if result.passed else "Failure"

    prompt_file_path = PROMPTS_DIR / f"{result.prompt_name}.txt"

    # Use relative links so VS Code and most Markdown viewers can open them
    test_file_link = _md_rel_path(result.suite_path, run_dir)
    prompt_file_link = _md_rel_path(prompt_file_path, run_dir)

    content = f"""
# {status_emoji} Test {status_text} Report: `{test_id}`

- **Test File**: [{result.suite_path}]({test_file_link})
- **Prompt File**: [{prompt_file_path}]({prompt_file_link})
- **Generation Model**: `{result.config.generation_model}`
- **Evaluation Model**: `{result.config.evaluation_model}`

## Request (Prompt + Values)
```text
{result.rendered_prompt.strip()}
```

## Criteria
> {result.test_case.criteria.strip()}

## Response
{result.response.strip()}

## Evaluation
> {result.evaluation.strip()}
    """.strip()

    report_path.write_text(content, encoding="utf-8")


def _render_failures(
    console: Console, results: List[TestResult], run_dir: Path
) -> None:
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
            suite_name = result.suite_path.stem
            test_id = result.test_case.id
            report_path = run_dir / f"{suite_name}-{test_id}.md"

            details_table = Table.grid(padding=(1, 2))
            details_table.add_column(style="bold blue", no_wrap=True)
            details_table.add_column()
            details_table.add_row(
                "Criteria:",
                _truncate_text(result.test_case.criteria, MAX_FAILURE_LINES),
            )
            details_table.add_row(
                "Response:", _truncate_text(result.response, MAX_FAILURE_LINES)
            )
            details_table.add_row(
                "Evaluation:", _truncate_text(result.evaluation, MAX_FAILURE_LINES)
            )
            details_table.add_row("Full Report:", f"[cyan]{report_path}[/cyan]")
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

    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = REPORTS_DIR / timestamp
    run_dir.mkdir()

    total_tests = sum(len(s.tests) for s in suites)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )

    console.print()
    with Live(progress, console=console, vertical_overflow="visible", transient=True):
        all_results: List[TestResult] = []
        overall_task = progress.add_task("[bold]Running tests", total=total_tests)

        for suite in suites:
            tasks = [
                _run_test_case(suite, tc, progress, overall_task) for tc in suite.tests
            ]
            suite_results = await asyncio.gather(*tasks)
            all_results.extend(suite_results)

    for result in all_results:
        _write_report_file(result, run_dir)

    latest_symlink = REPORTS_DIR / "latest"
    if latest_symlink.is_symlink() or latest_symlink.exists():
        latest_symlink.unlink()
    try:
        os.symlink(run_dir.name, latest_symlink, target_is_directory=True)
    except (OSError, AttributeError):  # Handle Windows/older Python
        try:
            os.symlink(run_dir.resolve(), latest_symlink, target_is_directory=True)
        except OSError:
            console.print(
                f"[yellow]Warning:[/yellow] Could not create 'latest' symlink to {run_dir}. "
                "This might be due to Windows permissions."
            )

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

    _render_failures(console, all_results, run_dir)

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
