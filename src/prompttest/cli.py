# src/prompttest/cli.py
import asyncio
import typer
from pathlib import Path

from . import runner, ui

app = typer.Typer(
    help="An automated testing framework for LLMs.",
)


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


@app.command(name="run")
def run_command():
    """
    Discovers and runs all tests in the `prompttests/` directory.
    """
    exit_code = asyncio.run(runner.run_all_tests())
    if exit_code > 0:
        raise typer.Exit(code=exit_code)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    If no command is specified, run the `run` command.
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(run_command)


if __name__ == "__main__":
    app()
