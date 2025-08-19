# src/prompttest/runner.py
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any, Dict, List

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
from .models import TestCase, TestResult, TestSuite


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

        response, gen_cached = await llm.generate(
            prompt_str, model, suite.config.temperature
        )
        progress.update(task_id, advance=0.5)

        eval_model = suite.config.evaluation_model
        if not eval_model:
            raise ValueError("`evaluation_model` is not defined.")
        passed, reason, eval_cached = await llm.evaluate(
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


async def run_all_tests() -> int:
    console = Console()
    start_time = time.perf_counter()
    try:
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

    run_dir = reporting.create_run_directory()
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
        reporting.write_report_file(result, run_dir)

    reporting.create_latest_symlink(run_dir, console)

    results_by_suite = defaultdict(list)
    for r in all_results:
        results_by_suite[r.suite_path].append(r)

    for i, suite in enumerate(suites):
        suite_results = results_by_suite[suite.file_path]
        ui.render_suite_header(console, suite)
        ui.render_suite_results(console, suite_results)
        if i < len(suites) - 1:
            console.print()

    ui.render_failures(console, all_results, run_dir)

    elapsed_time = time.perf_counter() - start_time
    passed_count = sum(1 for r in all_results if r.passed)
    failed_count = total_tests - passed_count

    ui.render_summary(console, total_tests, passed_count, elapsed_time)

    return 1 if failed_count > 0 else 0
