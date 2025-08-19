# src/prompttest/ui.py
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from rich import print
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .discovery import PROMPTS_DIR
from .models import TestResult, TestSuite

MAX_FAILURE_LINES = 3


def _truncate_text(text: str, max_lines: int) -> str:
    """Truncates text to a maximum number of lines, adding '[...]' if truncated."""
    lines = text.strip().splitlines()
    if len(lines) > max_lines:
        return "\n".join(lines[:max_lines]) + "\n[...]"
    return text


def render_failures(console: Console, results: List[TestResult], run_dir: Path) -> None:
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


def render_suite_header(console: Console, suite: TestSuite) -> None:
    """Renders the panel with test suite configuration details."""
    header_table = Table.grid(padding=(1, 2))
    header_table.add_column(style="bold blue")
    header_table.add_column()

    prompt_file_path = PROMPTS_DIR / f"{suite.prompt_name}.txt"

    header_table.add_row("Test File:", f"[cyan]{suite.file_path}[/cyan]")
    header_table.add_row("Prompt File:", f"[cyan]{prompt_file_path}[/cyan]")
    header_table.add_row("Generation Model:", suite.config.generation_model or "N/A")
    header_table.add_row("Evaluation Model:", suite.config.evaluation_model or "N/A")

    console.print(Panel(header_table, title="Test Info", expand=False, padding=(1, 2)))
    console.print()


def render_suite_results(console: Console, suite_results: List[TestResult]) -> None:
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


def render_summary(
    console: Console,
    total_tests: int,
    passed_count: int,
    elapsed_time: float,
) -> None:
    """Renders the final summary panel."""
    failed_count = total_tests - passed_count
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


def render_init_header() -> None:
    print()
    print("[bold]Initializing prompttest project[green]...[/green][/bold]")


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
            f"{path.parent.name}/{path.name}"
            if not path.name.startswith(".")
            else path.name
        )

        if warning:
            full_description = f"{description}[red]{warning}[/red]"
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
        )
    )
    print()
    print("[bold]3. Run `prompttest` to see your example tests run![/bold]")
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
