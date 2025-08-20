# src/prompttest/cli.py
import asyncio
from pathlib import Path
from typing import List, Tuple

import typer

from . import discovery, runner, ui

app = typer.Typer(help="An automated testing framework for LLMs.")


def _execute_run(
    *,
    patterns: List[str] | None,
    test_file: List[str] | None,
    test_id: List[str] | None,
    max_concurrency: int | None,
) -> int:
    """
    Shared path for running tests from both the 'run' command and the default callback.
    Preserves current behavior:
    - If no filters/max_concurrency are provided, call runner.run_all_tests() with no kwargs
      to keep tests expecting the exact call signature passing.
    - Otherwise, forward computed kwargs.
    """
    pos_file_globs, pos_id_globs = _classify_patterns(patterns or [])
    all_file_globs = (test_file or []) + pos_file_globs
    all_id_globs = (test_id or []) + pos_id_globs

    if all_file_globs or all_id_globs or max_concurrency is not None:
        return asyncio.run(
            runner.run_all_tests(
                test_file_globs=all_file_globs or None,
                test_id_globs=all_id_globs or None,
                max_concurrency=max_concurrency,
            )
        )
    return asyncio.run(runner.run_all_tests())


@app.command()
def init():
    """
    Initializes prompttest in the current directory with an example.
    This command is idempotent and non-destructive.
    """
    ui.render_init_header()

    gitignore_path = Path(".gitignore")
    if gitignore_path.is_dir():
        ui.render_error(
            "'.gitignore' exists but it is a directory. "
            "Please remove or rename it and run init again."
        )
        raise typer.Exit(code=1)

    try:
        templates_dir = Path(__file__).parent / "templates"
        env_template = (templates_dir / "_env.txt").read_text(encoding="utf-8")
        guide_template = (templates_dir / "_guide.md").read_text(encoding="utf-8")
        prompt_template = (templates_dir / "_customer_service.txt").read_text(
            encoding="utf-8"
        )
        global_config_template = (templates_dir / "_global_config.yml").read_text(
            encoding="utf-8"
        )
        main_suite_template = (templates_dir / "_main_suite.yml").read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as e:
        ui.render_template_error(e)
        raise typer.Exit(code=1)

    files_to_scaffold = [
        {
            "path": Path("prompts/customer_service.txt"),
            "content": prompt_template,
            "description": "Example prompt template",
        },
        {
            "path": Path("prompttests/prompttest.yml"),
            "content": global_config_template,
            "description": "Global configuration",
        },
        {
            "path": Path("prompttests/main.yml"),
            "content": main_suite_template,
            "description": "Example test suite",
        },
        {
            "path": Path("prompttests/GUIDE.md"),
            "content": guide_template,
            "description": "Quick-start guide",
        },
        {
            "path": Path(".env"),
            "content": env_template,
            "description": "Local environment variables ",
            "warning": "(DO NOT COMMIT)",
        },
        {
            "path": Path(".env.example"),
            "content": env_template,
            "description": "Environment variable template",
        },
    ]

    scaffold_report = []
    for file_spec in files_to_scaffold:
        path = file_spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(file_spec["content"], encoding="utf-8")
            status = "[dim green](created)[/dim green]"
        else:
            status = "[dim](exists, skipped)[/dim]"
        scaffold_report.append((file_spec, status))

    gitignore_definitions = [
        ("# prompttest cache", ".prompttest_cache/"),
        ("# Test reports", ".prompttest_reports/"),
        ("# Environment variables", ".env"),
    ]

    was_new = not gitignore_path.exists()
    content_before_append = ""
    if not was_new:
        content_before_append = gitignore_path.read_text(encoding="utf-8-sig")

    existing_lines = set(content_before_append.splitlines())
    entries_to_append = []
    for comment, entry in gitignore_definitions:
        if entry not in existing_lines:
            entries_to_append.append(f"{comment}\n{entry}")

    action = "Skipped"
    if entries_to_append:
        action = "Updated" if not was_new else "Created"
        eol = "\n"
        if not was_new:
            try:
                if b"\r\n" in gitignore_path.read_bytes():
                    eol = "\r\n"
            except Exception:
                pass
        prefix = ""
        if not was_new and content_before_append:
            if not content_before_append.endswith("\n"):
                prefix = eol * 2
            elif not content_before_append.endswith("\n\n"):
                prefix = eol
        normalized_entries = [s.replace("\n", eol) for s in entries_to_append]
        string_to_write = prefix + (eol * 2).join(normalized_entries) + eol
        with gitignore_path.open("a", encoding="utf-8", newline="") as f:
            f.write(string_to_write)

    if action == "Created":
        gitignore_display_status = "[dim green](created)[/dim green]"
    elif action == "Updated":
        gitignore_display_status = "[dim yellow](updated)[/dim yellow]"
    else:
        gitignore_display_status = "[dim](exists, skipped)[/dim]"

    ui.render_init_report(scaffold_report, gitignore_display_status)
    ui.render_init_next_steps()


def _classify_patterns(patterns: List[str]) -> Tuple[List[str], List[str]]:
    """
    Split positional patterns into file globs (under prompttests/) and test-id globs.
    Supports bare names (without .yml/.yaml) and subpaths.
    """
    id_globs: list[str] = []

    pt_dir = discovery.PROMPTTESTS_DIR
    pt_exists = pt_dir.is_dir()

    def has_sep(s: str) -> bool:
        return ("/" in s) or ("\\" in s)

    def has_yml_ext(s: str) -> bool:
        s2 = s.lower()
        return s2.endswith(".yml") or s2.endswith(".yaml")

    file_patterns: set[str] = set()

    for tok in patterns or []:
        if has_yml_ext(tok):
            file_patterns.add(tok)
            if not has_sep(tok):
                file_patterns.add(f"**/{tok}")
            continue

        if not pt_exists:
            id_globs.append(tok)
            continue

        candidates: list[str] = []
        if has_sep(tok):
            candidates += [tok, f"{tok}.yml", f"{tok}.yaml"]
        else:
            candidates += [
                tok,
                f"{tok}.yml",
                f"{tok}.yaml",
                f"**/{tok}.yml",
                f"**/{tok}.yaml",
            ]

        matched = False
        for c in candidates:
            matches = [p for p in pt_dir.rglob(c) if p.is_file()]
            if matches:
                matched = True
                if not has_sep(tok) and not has_yml_ext(tok):
                    file_patterns.add(f"**/{tok}.yml")
                    file_patterns.add(f"**/{tok}.yaml")
                else:
                    if has_yml_ext(c):
                        file_patterns.add(c)
                    else:
                        file_patterns.add(f"{tok}.yml")
                        file_patterns.add(f"{tok}.yaml")
                break

        if matched:
            continue

        id_globs.append(tok)

    return sorted(file_patterns), id_globs


@app.command(name="run")
def run_command(
    patterns: List[str] | None = typer.Argument(
        None,
        help="Positional filters: test-file globs (e.g., sub/*.yml) or test-id globs (e.g., check-*).",
    ),
    test_file: List[str] | None = typer.Option(
        None,
        "--test-file",
        help="Filter test files (globs) under 'prompttests/'. Repeatable.",
    ),
    test_id: List[str] | None = typer.Option(
        None,
        "--test-id",
        help="Filter test ids by glob. Repeatable.",
    ),
    max_concurrency: int | None = typer.Option(
        None,
        "--max-concurrency",
        min=1,
        help="Cap the number of test cases executed concurrently.",
    ),
):
    """
    Discovers and runs tests in the `prompttests/` directory.
    Positional patterns are a friendly shorthand for --test-file and --test-id.
    """
    exit_code = _execute_run(
        patterns=patterns,
        test_file=test_file,
        test_id=test_id,
        max_concurrency=max_concurrency,
    )
    if exit_code > 0:
        raise typer.Exit(code=exit_code)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    If no subcommand is provided, run the `run` command.
    We forward any leftover CLI args (ctx.args) as positional patterns to `run`.
    This avoids defining a positional Argument on the callback, which would
    otherwise swallow subcommands like `init`.
    """
    if ctx.invoked_subcommand is None:
        exit_code = _execute_run(
            patterns=list(ctx.args),
            test_file=None,
            test_id=None,
            max_concurrency=None,
        )

        if exit_code > 0:
            raise typer.Exit(code=exit_code)
