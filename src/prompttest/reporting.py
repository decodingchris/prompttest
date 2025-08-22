from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console

from .discovery import PROMPTS_DIR
from .models import TestResult

REPORTS_DIR = Path(".prompttest_reports")

_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*\r\n\t]')


def _sanitize_for_filename(s: str, fallback: str = "item") -> str:
    """
    Sanitize a string for safe cross-platform filenames.
    - Replace path separators and invalid characters with underscores.
    - Collapse repeated underscores and strip trailing dots/spaces/underscores.
    - Provide a fallback if everything is stripped out.
    """
    s = (s or "").strip()
    for ch in (os.sep, os.altsep) if os.altsep else (os.sep,):
        if ch:
            s = s.replace(ch, "_")
    s = _INVALID_CHARS_RE.sub("_", s)
    s = re.sub(r"_+", "_", s)
    s = s.strip("._ ")
    return s or fallback


def report_filename_for(result: TestResult) -> str:
    """Compute a safe filename for a test result's Markdown report."""
    suite_name = _sanitize_for_filename(result.suite_path.stem, "suite")
    test_id = _sanitize_for_filename(result.test_case.id, "test")
    return f"{suite_name}-{test_id}.md"


def report_path_for(result: TestResult, run_dir: Path) -> Path:
    """Compute the full path (under run_dir) for a result's report file."""
    return run_dir / report_filename_for(result)


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
    report_path = report_path_for(result, run_dir)

    status_emoji = "✅" if result.passed else "❌"
    status_text = "Pass" if result.passed else "Failure"

    prompt_file_path = PROMPTS_DIR / f"{result.prompt_name}.txt"
    test_file_link = _md_rel_path(result.suite_path, run_dir)
    prompt_file_link = _md_rel_path(prompt_file_path, run_dir)

    crit_lines = (result.test_case.criteria or "").strip().splitlines() or [""]
    criteria_block = "\n".join(f"> {line}" if line else ">" for line in crit_lines)

    eval_lines = (result.evaluation or "").strip().splitlines() or [""]
    evaluation_block = "\n".join(f"> {line}" if line else ">" for line in eval_lines)

    content = f"""
# {status_emoji} Test {status_text} Report: `{result.test_case.id}`

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
{criteria_block}

## Response
{result.response.strip()}

## Evaluation
{evaluation_block}
    """.strip()

    report_path.write_text(content, encoding="utf-8")
