from __future__ import annotations

from pathlib import Path

import pytest

import prompttest.cli as cli
from prompttest.cli import app


@pytest.mark.parametrize(
    "missing_filename",
    [
        "_env.txt",
        "_guide.md",
        "_customer_service.txt",
        "_global_config.yml",
        "_main_suite.yml",
    ],
)
def test_init_exits_with_code_1_when_a_template_file_is_missing(
    monkeypatch, runner, in_tmp_project: Path, missing_filename: str
):
    templates_dir = Path(cli.__file__).parent / "templates"
    missing_path = templates_dir / missing_filename

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):
        if self == missing_path:
            raise FileNotFoundError(2, "No such file or directory", str(missing_path))
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(cli.Path, "read_text", fake_read_text)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 1
    assert "Error:" in result.stdout and "Template file not found" in result.stdout
    assert missing_filename in result.stdout


def test_init_bubbles_up_permission_error_on_file_write(
    monkeypatch, runner, in_tmp_project: Path
):
    original_write_text = Path.write_text

    def fake_write_text(self: Path, *args, **kwargs):
        if self.name == ".env":
            raise PermissionError("Permission denied: .env")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(cli.Path, "write_text", fake_write_text)

    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert isinstance(result.exception, PermissionError)
    assert "Permission denied: .env" in str(result.exception)


def test_init_handles_gitignore_append_permission_error(
    monkeypatch, runner, in_tmp_project: Path
):
    (in_tmp_project / ".gitignore").touch()
    original_open = Path.open

    def fake_open(self: Path, mode: str = "r", *args, **kwargs):
        if self.name == ".gitignore" and "a" in mode:
            raise PermissionError("Permission denied for appending to .gitignore")
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)

    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    assert isinstance(result.exception, PermissionError)
    assert "appending to .gitignore" in str(result.exception)


def test_init_handles_gitignore_with_unicode_and_null_byte(
    runner, in_tmp_project: Path
):
    gi = in_tmp_project / ".gitignore"
    gi.write_text("prelude ☃\x00\n", encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    expected = "prelude ☃\x00\n\n# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n"
    assert gi.read_text(encoding="utf-8") == expected


def test_init_exits_gracefully_if_gitignore_is_a_directory(
    runner, in_tmp_project: Path
):
    (in_tmp_project / ".gitignore").mkdir()

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "Error:" in result.stdout
    assert ".gitignore' exists but it is a directory" in result.stdout

    assert not (in_tmp_project / "prompts").exists()
    assert not (in_tmp_project / "prompttests").exists()
    assert not (in_tmp_project / ".env").exists()


def test_init_exits_with_code_1_when_template_missing_without_filename(
    monkeypatch, runner, in_tmp_project: Path
):
    import prompttest.cli as cli

    templates_dir = Path(cli.__file__).parent / "templates"
    missing_path = templates_dir / "_env.txt"

    original_read_text = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):
        if self == missing_path:
            raise FileNotFoundError("No such file or directory")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(cli.Path, "read_text", fake_read_text)

    result = runner.invoke(cli.app, ["init"])
    assert result.exit_code == 1
    assert "Template file not found: None" in result.stdout
    assert (
        "Please ensure you are running a valid installation of prompttest."
        in result.stdout
    )
