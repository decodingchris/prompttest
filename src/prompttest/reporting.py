from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console

from .discovery import PROMPTS_DIR
from .models import TestResult

REPORTS_DIR = Path(".prompttest_reports")


def create_run_directory() -> Path:
    """Creates the main reports directory and a timestamped subdirectory for the current run."""
    REPORTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
    run_dir = REPORTS_DIR / timestamp
    if run_dir.exists():
        i = 1
        while True:
            alt_dir = REPORTS_DIR / f"{timestamp}-{i}"
            if not alt_dir.exists():
                run_dir = alt_dir
                break
            i += 1
    run_dir.mkdir()
    return run_dir


def create_latest_symlink(run_dir: Path, console: Console) -> None:
    """Creates/updates a 'latest' symlink pointing to the most recent run directory."""
    latest_symlink = REPORTS_DIR / "latest"
    if latest_symlink.is_symlink():
        try:
            latest_symlink.unlink()
        except OSError:
            console.print(
                "[yellow]Warning:[/yellow] Could not remove existing symlink 'latest'."
            )
            return
    elif latest_symlink.exists():
        try:
            if latest_symlink.is_dir():
                latest_symlink.rmdir()
            else:
                latest_symlink.unlink()
        except OSError:
            console.print(
                f"[yellow]Warning:[/yellow] Cannot replace existing 'latest' at {latest_symlink}. "
                "It is not a symlink and could not be removed."
            )
            return
    try:
        os.symlink(run_dir.name, latest_symlink, target_is_directory=True)
    except (OSError, AttributeError):
        try:
            os.symlink(run_dir.resolve(), latest_symlink, target_is_directory=True)
        except OSError:
            console.print(
                f"[yellow]Warning:[/yellow] Could not create 'latest' symlink to {run_dir}. "
                "This might be due to Windows permissions."
            )
            try:
                if latest_symlink.exists():
                    if latest_symlink.is_dir() and not latest_symlink.is_symlink():
                        shutil.rmtree(latest_symlink)
                    else:
                        latest_symlink.unlink()
                shutil.copytree(run_dir, latest_symlink)
            except Exception:
                pass


def _md_rel_path(target: Path, start: Path) -> str:
    """Return a Markdown-friendly relative path (POSIX-style slashes)."""
    rel = os.path.relpath(target.resolve(), start.resolve())
    return rel.replace(os.sep, "/")


def write_report_file(result: TestResult, run_dir: Path) -> None:
    """Writes a detailed .md file for a single test result."""
    suite_name = result.suite_path.stem
    test_id = result.test_case.id
    filename = f"{suite_name}-{test_id}.md"
    report_path = run_dir / filename

    status_emoji = "✅" if result.passed else "❌"
    status_text = "Pass" if result.passed else "Failure"

    prompt_file_path = PROMPTS_DIR / f"{result.prompt_name}.txt"
    test_file_link = _md_rel_path(result.suite_path, run_dir)
    prompt_file_link = _md_rel_path(prompt_file_path, run_dir)

    content = f"""
# {status_emoji} Test {status_text} Report: `{test_id}`

- **Test File**: [{result.suite_path}]({test_file_link})

- **Prompt File**: [{prompt_file_path}]({prompt_file_link})

- **Generation Model**: `{result.config.generation_model}`

- **Generation Temperature**: `{result.config.generation_temperature}`

- **Evaluation Model**: `{result.config.evaluation_model}`

- **Evaluation Temperature**: `{result.config.evaluation_temperature}`

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
