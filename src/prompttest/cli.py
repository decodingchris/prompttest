import asyncio
import typer
from pathlib import Path
from rich import print
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from . import runner

app = typer.Typer(
    help="An automated testing framework for LLMs.",
)


@app.command()
def init():
    """
    Initializes a new prompttest project with an example.
    This command is idempotent and non-destructive.
    """
    print()
    print("[bold]Initializing prompttest project[green]...[/green][/bold]")

    gitignore_path = Path(".gitignore")
    if gitignore_path.is_dir():
        print(
            "[bold red]Error:[/bold red] '.gitignore' exists but it is a directory. "
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
        error_message = Text.from_markup(
            f"[bold red]Error:[/bold red] Template file not found: {e.filename}"
        )
        error_message.no_wrap = True
        error_message.overflow = "ignore"
        print(error_message)
        if e.filename:
            print(Path(e.filename).name)
        print("Please ensure you are running a valid installation of prompttest.")
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

    report = []
    for file_spec in files_to_scaffold:
        path = file_spec["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(file_spec["content"], encoding="utf-8")
            status = "[dim green](created)[/dim green]"
        else:
            status = "[dim](exists, skipped)[/dim]"
        report.append((file_spec, status))

    gitignore_definitions = [
        ("# prompttest cache", ".prompttest_cache/"),
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
        f"  - [bold]{'.gitignore':<30}[/bold] {'Files for Git to ignore':<45} {gitignore_display_status}"
    )
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
