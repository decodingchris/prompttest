from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich import box
from rich import print
from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import reporting
from .discovery import PROMPTS_DIR
from .models import TestResult, TestSuite

MAX_FAILURE_LINES = 3


def _truncate_text(text: str, max_lines: int) -> str:
    """Truncates text to a maximum number of lines, adding '[...]' if truncated."""
    clean_text = text.strip()
    lines = clean_text.splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n[...]"
    return clean_text


def render_project_not_initialized(console: Console) -> None:
    """Renders a helpful error message when 'prompttests' is not found."""
    console.print("[bold red]Error:[/bold red] Directory 'prompttests' not found.")
    console.print("\nTo get started, initialize prompttest with:")
    console.print("\n  [bold cyan]prompttest init[/bold cyan]\n")


def _create_failure_panels(results: List[TestResult], run_dir: Path) -> List[Panel]:
    """Creates a list of panels for each failed test."""
    failures = [r for r in results if not r.passed]
    if not failures:
        return []

    panels = []
    for result in failures:
        failure_title = f"[bold red]❌ {result.test_case.id}[/bold red]"
        content: Any
        if result.error:
            msg = result.error or ""
            is_api_error = result.error_kind == "llm"
            label = "API Error" if is_api_error else "Error"
            text = f"[bold red]{label}:[/bold red] {msg}"
            if is_api_error:
                text += (
                    "\n\n[dim]Tip: This is often a temporary issue with the model provider. "
                    "Try running the test again in a few moments.[/dim]"
                )
            content = Text.from_markup(text)
        else:
            report_path = reporting.report_path_for(result, run_dir)

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
                "Evaluation:",
                f"[bold orange1]{_truncate_text(result.evaluation, MAX_FAILURE_LINES)}[/bold orange1]",
            )
            details_table.add_row("Full Report:", f"[cyan]{report_path}[/cyan]")
            content = details_table

        panels.append(
            Panel(
                content,
                title=failure_title,
                title_align="left",
                border_style="red",
                expand=False,
                padding=(1, 2),
                box=box.HEAVY,
            )
        )
    return panels


def render_suite_report(
    console: Console, suite: TestSuite, suite_results: List[TestResult], run_dir: Path
) -> None:
    """Renders a single, unified panel for a test suite's results, details, and failures."""

    prompt_file_path = PROMPTS_DIR / f"{suite.prompt_name}.txt"
    config_table = Table.grid(padding=(1, 2))
    config_table.add_column(style="blue")
    config_table.add_column(style="white")
    config_table.add_row("[bold]Prompt File:[/bold]", str(prompt_file_path))
    config_table.add_row(
        "[bold]Generation Model:[/bold]", suite.config.generation_model or "N/A"
    )
    config_table.add_row(
        "[bold]Generation Temperature:[/bold]", str(suite.config.generation_temperature)
    )
    config_table.add_row(
        "[bold]Evaluation Model:[/bold]", suite.config.evaluation_model or "N/A"
    )
    config_table.add_row(
        "[bold]Evaluation Temperature:[/bold]", str(suite.config.evaluation_temperature)
    )

    result_lines = []
    for result in suite_results:
        cached_tag = " [dim](cached)[/dim]" if result.is_cached else ""
        if result.passed:
            result_lines.append(
                f"[bold green]✅ PASS: {result.test_case.id}[/bold green]{cached_tag}"
            )
        else:
            result_lines.append(
                f"[bold red]❌ FAIL: {result.test_case.id}[/bold red]{cached_tag}"
            )
    results_text = Text.from_markup("\n\n".join(result_lines))

    passed_count = sum(1 for r in suite_results if r.passed)
    failed_count = len(suite_results) - passed_count
    subtitle_parts = []
    if failed_count > 0:
        subtitle_parts.append(f"[bold red]{failed_count} failed[/bold red]")
    if passed_count > 0:
        subtitle_parts.append(f"[bold green]{passed_count} passed[/bold green]")
    subtitle_text = Text.from_markup(", ".join(subtitle_parts))

    failure_panels = _create_failure_panels(suite_results, run_dir)

    report_items: List[RenderableType] = [
        config_table,
        "",
        "",
        results_text,
    ]
    if failure_panels:
        report_items.append("")
        report_items.append("")
        for i, panel in enumerate(failure_panels):
            report_items.append(panel)
            if i < len(failure_panels) - 1:
                report_items.append("")

    report_group = Group(*report_items)

    console.print(
        Panel(
            report_group,
            title=f"[bold yellow]{suite.file_path}[/bold yellow]",
            title_align="left",
            subtitle=subtitle_text,
            subtitle_align="right",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )


def render_summary(
    console: Console, all_results: List[TestResult], elapsed_time: float
) -> None:
    """Renders the final, conclusive summary panel for the entire run."""
    total_tests = len(all_results)
    if total_tests == 0:
        return

    total_passed = sum(1 for r in all_results if r.passed)
    total_failed = total_tests - total_passed
    total_cached = sum(1 for r in all_results if r.is_cached)
    pass_rate = (total_passed / total_tests) * 100 if total_tests else 0.0

    parts = []
    if total_failed > 0:
        parts.append(f"[bold red]{total_failed} failed[/bold red]")
    if total_passed > 0:
        parts.append(f"[bold green]{total_passed} passed[/bold green]")

    summary_line = f"{', '.join(parts)} in {elapsed_time:.2f}s"
    if total_tests > 0:
        summary_line += f" • [bold]{pass_rate:.0f}% pass rate[/bold]"
    if total_cached > 0:
        summary_line += f" • [dim]{total_cached} cached[/dim]"

    summary_text = Text.from_markup(summary_line)

    border_color = "red" if total_failed > 0 else "green"

    renderables: List[RenderableType] = [summary_text]
    if total_failed > 0:
        failures = [r for r in all_results if not r.passed]
        failures.sort(key=lambda r: (str(r.suite_path), r.test_case.id))

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold yellow", no_wrap=True)
        table.add_column(style="bold red", no_wrap=True)
        table.add_column(style="bold orange1")

        for idx, r in enumerate(failures):
            reason = _truncate_text(r.evaluation or r.error or "", max_lines=1)
            table.add_row(str(r.suite_path), r.test_case.id, reason or "[dim]n/a[/dim]")
            if idx < len(failures) - 1:
                table.add_row("", "", "")

        renderables.extend(["", table])

    console.print(
        Panel(
            Group(*renderables),
            title="[bold]Test Summary[/bold]",
            title_align="left",
            box=box.HEAVY,
            padding=(1, 2),
            expand=False,
            border_style=border_color,
        )
    )


def render_init_header() -> None:
    print()
    print("[bold]Initializing prompttest[green]...[/green][/bold]")


def render_init_report(
    report: List[Tuple[Dict[str, Any], str]], gitignore_status: str
) -> None:
    print()
    print("[bold green]Successfully initialized prompttest![/bold green]")
    print()
    print("Project structure:")
    for file_spec, status in report:
        description = file_spec.get("description", "An example test file")
        warning = file_spec.get("warning")
        path = file_spec["path"]

        display_path = (
            str(path).replace("\\", "/") if not path.name.startswith(".") else path.name
        )
        if warning:
            full_description = f"{description} [red]{warning}[/red]"
            print(
                f"  - [bold]{display_path:<30}[/bold] {full_description:<56} {status}"
            )
        else:
            print(f"  - [bold]{display_path:<30}[/bold] {description:<45} {status}")

    print(
        f"  - [bold]{'.gitignore':<30}[/bold] {'Files for Git to ignore':<45} {gitignore_status}"
    )


def render_init_next_steps() -> None:
    print()
    print("[bold]Next steps:[/bold]")
    print()
    print("[bold]1. Get your OpenRouter API key[/bold]")
    print()
    print("   [grey50]prompttest uses OpenRouter to give you access to a wide[/grey50]")
    print(
        "   [grey50]range of LLMs (including free models) with a single API key.[/grey50]"
    )
    print()
    print(
        "   Get yours at: [link=https://openrouter.ai/keys]https://openrouter.ai/keys[/link]"
    )
    panel_group = Group(
        Text.from_markup(
            "Open the [bold cyan].env[/bold cyan] file and ensure it contains:"
        ),
        Text.from_markup(
            "\n  [grey50]OPENROUTER_API_KEY=[/grey50][yellow]your_key_here[/yellow]"
        ),
        Text.from_markup(
            "\nReplace [yellow]your_key_here[/yellow] with your actual key."
        ),
    )
    print()
    print("[bold]2. Add your API key to the `.env` file:[/bold]")
    print()
    print(
        Panel(
            panel_group,
            title="[bold]API Key Setup[/bold]",
            border_style="blue",
            expand=False,
            padding=(1, 2),
            box=box.HEAVY,
        )
    )
    print()
    print("[bold]3. Run [blue]prompttest[/blue] to see your example tests run![/bold]")
    print()
    print(
        "   [dim]The examples are configured to be run for free (with a free model).[/dim]"
    )
    print("   [dim]For sensitive data, consider a paid model as free providers[/dim]")
    print("   [dim]may use your prompts and completions for training.[/dim]")
    print()
    print("[bold]4. Edit the files to start building your own tests.[/bold]")
    print()
    print(
        "[bold]5. Check out [cyan]prompttests/GUIDE.md[/cyan] for more details.[/bold]"
    )
    print()
    print("[bold]Happy testing[green]![/green][/bold]")
    print()


def render_error(message: str) -> None:
    print(f"[bold red]Error:[/bold red] {message}")


def render_template_error(error: FileNotFoundError) -> None:
    error_message = Text.from_markup(
        f"[bold red]Error:[/bold red] Template file not found: {error.filename}"
    )
    error_message.no_wrap = True
    error_message.overflow = "ignore"
    print(error_message, file=sys.stderr)
    if error.filename:
        print(Path(error.filename).name, file=sys.stderr)
    print(
        "Please ensure you are running a valid installation of prompttest.",
        file=sys.stderr,
    )
