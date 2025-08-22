import asyncio
from pathlib import Path
from typing import List, Tuple

import typer

from . import runner, ui


app = typer.Typer(
    help="An automated testing framework for LLMs.",
    invoke_without_command=True,
    no_args_is_help=False,
)


def _execute_run(
    *,
    patterns: List[str] | None,
    test_file: List[str] | None,
    test_id: List[str] | None,
    max_concurrency: int | None,
) -> int:
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


@app.command(help="Setup prompttest in the current directory.")
def init():
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
        example_suite_template = (templates_dir / "_test_customers.yml").read_text(
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
            "path": Path("prompttests/test_customers.yml"),
            "content": example_suite_template,
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
    Classify positional tokens according to simple, explicit rules:
    - dir: token ends with slash OR contains a slash and no .yml/.yaml -> recursive directory
    - file: token ends with .yml or .yaml
    - id: otherwise
    """
    file_globs: set[str] = set()
    id_globs: list[str] = []

    def has_sep(s: str) -> bool:
        return ("/" in s) or ("\\" in s)

    def has_yml_ext(s: str) -> bool:
        s2 = s.lower()
        return s2.endswith(".yml") or s2.endswith(".yaml")

    for raw in patterns or []:
        tok = (raw or "").strip()
        if not tok:
            continue

        if tok.endswith(("/", "\\")) or (has_sep(tok) and not has_yml_ext(tok)):
            t = tok.rstrip("/\\")
            if t:
                file_globs.add(f"{t}/*.yml")
                file_globs.add(f"{t}/*.yaml")
                file_globs.add(f"{t}/**/*.yml")
                file_globs.add(f"{t}/**/*.yaml")
                if not has_sep(t):
                    file_globs.add(f"**/{t}/*.yml")
                    file_globs.add(f"**/{t}/*.yaml")
                    file_globs.add(f"**/{t}/**/*.yml")
                    file_globs.add(f"**/{t}/**/*.yaml")
            continue

        if has_yml_ext(tok):
            file_globs.add(tok)
            if not has_sep(tok):
                file_globs.add(f"**/{tok}")
            continue

        id_globs.append(tok)

    return sorted(file_globs), id_globs


@app.command(
    name="run",
    help="Run tests. Filter by directory (e.g., customers/), file (test_customers.yml), or test ID (check-*).",
)
def run_command(
    patterns: List[str] | None = typer.Argument(
        None,
        help="Positional filters: dir/ (or nested/dir), file.yml, or id globs (e.g., check-*).",
    ),
    dir_: List[str] | None = typer.Option(
        None, "--dir", help="Directory under 'prompttests/' (recursive). Repeatable."
    ),
    file: List[str] | None = typer.Option(
        None, "--file", help="File or file glob under 'prompttests/'. Repeatable."
    ),
    id_: List[str] | None = typer.Option(
        None, "--id", help="Test id glob. Repeatable."
    ),
    max_concurrency: int | None = typer.Option(
        None,
        "--max-concurrency",
        min=0,
        help="Cap concurrent test cases (default: 8). Use 0 for unlimited.",
        show_default=False,
    ),
):
    pos_file_globs, pos_id_globs = _classify_patterns(patterns or [])

    dir_file_globs: list[str] = []
    for d in dir_ or []:
        t = (d or "").strip().rstrip("/\\")
        if not t:
            continue
        dir_file_globs += [f"{t}/*.yml", f"{t}/*.yaml"]
        dir_file_globs += [f"{t}/**/*.yml", f"{t}/**/*.yaml"]
        if "/" not in t and "\\" not in t:
            dir_file_globs += [
                f"**/{t}/*.yml",
                f"**/{t}/*.yaml",
                f"**/{t}/**/*.yml",
                f"**/{t}/**/*.yaml",
            ]

    file_globs: list[str] = []
    for f in file or []:
        f2 = (f or "").strip()
        if not f2:
            continue
        lower = f2.lower()
        if lower.endswith(".yml") or lower.endswith(".yaml"):
            if "/" not in f2 and "\\" not in f2:
                file_globs.append(f"**/{f2}")
            file_globs.append(f2)
        else:
            file_globs.append(f2)

    all_file_globs = dir_file_globs + file_globs + pos_file_globs
    all_id_globs = (id_ or []) + pos_id_globs

    exit_code = _execute_run(
        patterns=None,
        test_file=all_file_globs or None,
        test_id=all_id_globs or None,
        max_concurrency=max_concurrency,
    )
    if exit_code > 0:
        raise typer.Exit(code=exit_code)


@app.callback(
    invoke_without_command=True,
)
def main(
    ctx: typer.Context,
    max_concurrency: int | None = typer.Option(
        None,
        "--max-concurrency",
        min=0,
        help="Cap concurrent test cases (default: 8). Use 0 for unlimited.",
        show_default=False,
    ),
):
    if ctx.invoked_subcommand is None:
        exit_code = _execute_run(
            patterns=None,
            test_file=None,
            test_id=None,
            max_concurrency=max_concurrency,
        )

        if exit_code > 0:
            raise typer.Exit(code=exit_code)
