from __future__ import annotations

import asyncio
import fnmatch
import re
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)

from . import discovery, llm, reporting, ui
from .llm import LLMError
from .models import TestCase, TestResult, TestSuite

_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")
DEFAULT_MAX_CONCURRENCY = 8


def _format_prompt(template: str, inputs: Dict[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return str(inputs.get(key, m.group(0)))

    return _PLACEHOLDER_RE.sub(repl, template)


async def _run_test_case(
    suite: TestSuite, test_case: TestCase, progress: Progress, task_id: TaskID
) -> TestResult:
    prompt_str = ""
    try:
        prompt_str = _format_prompt(suite.prompt_content, test_case.inputs)
        model = suite.config.generation_model
        if not model:
            raise ValueError("`generation_model` is not defined.")

        response, gen_cached = await llm.generate(
            prompt_str, model, suite.config.generation_temperature
        )
        progress.update(task_id, advance=0.5)

        eval_model = suite.config.evaluation_model
        if not eval_model:
            raise ValueError("`evaluation_model` is not defined.")
        passed, reason, eval_cached = await llm.evaluate(
            response,
            test_case.criteria,
            eval_model,
            suite.config.evaluation_temperature,
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
    except LLMError as e:
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
            error_kind="llm",
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


def _match_any(value: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(value, pat) for pat in patterns)


def _suite_matches_globs(suite: TestSuite, globs: List[str]) -> bool:
    if not globs:
        return True
    full = str(suite.file_path)
    name = suite.file_path.name
    try:
        rel = str(suite.file_path.relative_to(discovery.PROMPTTESTS_DIR))
    except Exception:
        rel = name
    return _match_any(full, globs) or _match_any(rel, globs) or _match_any(name, globs)


async def run_all_tests(
    *,
    test_file_globs: Optional[List[str]] = None,
    test_id_globs: Optional[List[str]] = None,
    max_concurrency: Optional[int] = None,
) -> int:
    console = Console()
    start_time = time.perf_counter()
    try:
        discovery.clear_caches()
        suites = discovery.discover_and_prepare_suites()
    except FileNotFoundError as e:
        if discovery.PROMPTTESTS_DIR.name in str(e):
            ui.render_project_not_initialized(console)
        else:
            console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    except (ValueError, EnvironmentError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return 1
    except Exception:
        console.print_exception(show_locals=True)
        return 1

    if not suites:
        console.print("[yellow]No tests found.[/yellow]")
        return 0

    test_file_globs = test_file_globs or []
    test_id_globs = test_id_globs or []

    if test_file_globs:
        suites = [s for s in suites if _suite_matches_globs(s, test_file_globs)]
    if test_id_globs:
        for s in suites:
            s.tests = [t for t in s.tests if _match_any(t.id, test_id_globs)]
        suites = [s for s in suites if s.tests]

    if not suites:
        console.print("[yellow]No tests found.[/yellow]")
        return 0

    run_dir = reporting.create_run_directory()
    total_tests = sum(len(s.tests) for s in suites)
    progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )

    console.print()

    if max_concurrency == 0:
        limit = None
    else:
        limit = (
            max_concurrency if max_concurrency is not None else DEFAULT_MAX_CONCURRENCY
        )
    sem: Optional[asyncio.Semaphore] = asyncio.Semaphore(limit) if limit else None

    async def _maybe_bounded(coro):
        if sem is None:
            return await coro
        async with sem:
            return await coro

    with Live(progress, console=console, vertical_overflow="visible", transient=True):
        overall_task = progress.add_task("[bold]Running tests", total=total_tests)
        tasks = [
            _maybe_bounded(_run_test_case(suite, tc, progress, overall_task))
            for suite in suites
            for tc in suite.tests
        ]
        all_results: List[TestResult] = await asyncio.gather(*tasks)

    for result in all_results:
        reporting.write_report_file(result, run_dir)

    reporting.create_latest_symlink(run_dir, console)

    results_by_suite = defaultdict(list)
    for r in all_results:
        results_by_suite[r.suite_path].append(r)

    sorted_suites = sorted(suites, key=lambda s: s.file_path)

    for suite in sorted_suites:
        suite_results = results_by_suite[suite.file_path]
        ui.render_suite_report(console, suite, suite_results, run_dir)
        console.print()

    elapsed_time = time.perf_counter() - start_time
    ui.render_summary(console, all_results, elapsed_time)
    console.print()

    failed_count = sum(1 for r in all_results if not r.passed)
    return 1 if failed_count > 0 else 0
