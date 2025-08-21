from __future__ import annotations

from pathlib import Path

import click
import pytest

import prompttest.cli as cli_mod
from prompttest.cli import app


def test_init_creates_files_with_exact_contents_and_summary(
    runner, in_tmp_project: Path, template_texts
):
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 0, res.stdout

    for rel_path, expected in template_texts.items():
        p = in_tmp_project / rel_path
        assert p.exists()
        assert p.read_text(encoding="utf-8") == expected

    gi = in_tmp_project / ".gitignore"
    assert gi.exists()
    assert gi.read_text(encoding="utf-8") == (
        "# prompttest cache\n"
        ".prompttest_cache/\n\n"
        "# Test reports\n"
        ".prompttest_reports/\n\n"
        "# Environment variables\n"
        ".env\n"
    )

    out = res.stdout
    assert "Initializing prompttest" in out
    assert "Successfully initialized prompttest!" in out
    assert "Project structure:" in out
    assert "prompts/customer_service.txt" in out
    assert ".env" in out and "DO NOT COMMIT" in out
    assert ".gitignore" in out and "(created)" in out
    assert "Next steps:" in out
    assert "Run prompttest to see your example tests run!" in out


def test_init_is_idempotent_and_skips_existing_files(
    runner, in_tmp_project: Path, template_texts
):
    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0

    snapshot = {
        rel: (in_tmp_project / rel).read_text(encoding="utf-8")
        for rel in template_texts
    }

    second = runner.invoke(app, ["init"])
    assert second.exit_code == 0

    for rel_path, before in snapshot.items():
        after = (in_tmp_project / rel_path).read_text(encoding="utf-8")
        assert after == before

    out = second.stdout
    assert out.count("(exists, skipped)") >= 6
    assert ".gitignore" in out and "(exists, skipped)" in out


@pytest.mark.parametrize(
    "initial, expected, status_id",
    [
        (
            None,
            "# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(created)",
        ),
        (
            "foo",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(updated)",
        ),
        (
            "foo\n",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(updated)",
        ),
        (
            "foo\n\n",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(updated)",
        ),
        (
            "# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(exists, skipped)",
        ),
        (
            "foo\n.env\n",
            "foo\n.env\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n",
            "(updated)",
        ),
        (
            "\ufeff.env\n",
            "\ufeff.env\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n",
            "(updated)",
        ),
        (
            ".env \n",
            ".env \n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(updated)",
        ),
        (
            "config/.env.production\n",
            "config/.env.production\n\n# prompttest cache\n.prompttest_cache/\n\n# Test reports\n.prompttest_reports/\n\n# Environment variables\n.env\n",
            "(updated)",
        ),
    ],
)
def test_gitignore_update_variants(
    runner, in_tmp_project: Path, initial, expected, status_id
):
    gi = in_tmp_project / ".gitignore"
    if initial is not None:
        gi.write_text(initial, encoding="utf-8")
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 0
    assert gi.read_text(encoding="utf-8") == expected
    assert ".gitignore" in res.stdout
    assert any(
        marker in res.stdout
        for marker in ["(created)", "(updated)", "(exists, skipped)"]
    )


def test_init_exits_gracefully_if_gitignore_is_a_directory(
    runner, in_tmp_project: Path
):
    (in_tmp_project / ".gitignore").mkdir()
    res = runner.invoke(app, ["init"])
    assert res.exit_code == 1
    assert "Error:" in res.stdout
    assert ".gitignore' exists but it is a directory" in res.stdout
    assert not (in_tmp_project / "prompts").exists()


def test_init_template_missing_reports_filename(
    monkeypatch, in_tmp_project: Path, capsys
):
    tdir = Path(cli_mod.__file__).parent / "templates"
    missing = tdir / "_main_suite.yml"
    orig = Path.read_text

    def fake_read_text(self: Path, *args, **kwargs):
        if self == missing:
            raise FileNotFoundError(2, "No such file or directory", str(missing))
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(cli_mod.Path, "read_text", fake_read_text)

    with pytest.raises(click.exceptions.Exit) as excinfo:
        cli_mod.init()

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Template file not found" in captured.err
    assert "_main_suite.yml" in captured.err


def test_init_bubbles_up_permission_error_on_file_write(
    monkeypatch, runner, in_tmp_project: Path
):
    orig_write = Path.write_text

    def fake_write_text(self: Path, *args, **kwargs):
        if self.name == ".env":
            raise PermissionError("Permission denied: .env")
        return orig_write(self, *args, **kwargs)

    monkeypatch.setattr(cli_mod.Path, "write_text", fake_write_text)
    res = runner.invoke(app, ["init"])
    assert res.exit_code != 0
    assert isinstance(res.exception, PermissionError)
    assert "Permission denied: .env" in str(res.exception)
