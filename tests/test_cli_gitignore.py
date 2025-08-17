from __future__ import annotations

from pathlib import Path

import pytest

from prompttest.cli import app


@pytest.mark.parametrize(
    "initial, expected_suffix, expected_status, case_id",
    [
        pytest.param(
            None,
            "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(created)",
            "missing-file",
            id="missing-file",
        ),
        pytest.param(
            "foo",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(updated)",
            "ends-with-no-newline",
            id="ends-with-no-newline",
        ),
        pytest.param(
            "foo\n",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(updated)",
            "ends-with-one-newline",
            id="ends-with-one-newline",
        ),
        pytest.param(
            "foo\n\n",
            "foo\n\n# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(updated)",
            "ends-with-two-newlines",
            id="ends-with-two-newlines",
        ),
        pytest.param(
            "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(exists, skipped)",
            "already-has-entries",
            id="already-has-entries",
        ),
        pytest.param(
            "foo\n.env\n",
            "foo\n.env\n\n# prompttest cache\n.prompttest_cache/\n",
            "(updated)",
            "has-one-entry-missing",
            id="has-one-entry-missing",
        ),
        pytest.param(
            "foo\r\n.env\r\n",
            "foo\n.env\n\n# prompttest cache\n.prompttest_cache/\n",
            "(updated)",
            "handles-crlf-line-endings",
            id="handles-crlf-line-endings",
        ),
        pytest.param(
            "\ufeff.env\n",
            "\ufeff.env\n\n# prompttest cache\n.prompttest_cache/\n",
            "(updated)",
            "handles-utf8-bom",
            id="handles-utf8-bom",
        ),
        pytest.param(
            ".env \n",
            ".env \n\n# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n",
            "(updated)",
            "whitespace-is-not-a-match",
            id="whitespace-is-not-a-match",
        ),
    ],
)
def test_gitignore_update_logic_precise(
    runner, in_tmp_project: Path, initial, expected_suffix, expected_status, case_id
):
    gi = in_tmp_project / ".gitignore"
    if initial is not None:
        gi.write_text(initial, encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    actual = gi.read_text(encoding="utf-8")
    assert actual == expected_suffix

    out = result.stdout
    assert ".gitignore" in out
    assert expected_status in out, f"Case {case_id}: wrong status reported"


def test_gitignore_respects_existing_content_and_appends_once(
    runner, in_tmp_project: Path
):
    gi = in_tmp_project / ".gitignore"
    gi.write_text("node_modules/\n.DS_Store\n")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    content = gi.read_text()
    expected = (
        "node_modules/\n.DS_Store\n\n"
        "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n"
    )
    assert content == expected

    result2 = runner.invoke(app, ["init"])
    assert result2.exit_code == 0
    assert gi.read_text() == expected


def test_gitignore_update_is_not_fooled_by_substrings(runner, in_tmp_project: Path):
    gi = in_tmp_project / ".gitignore"
    initial_content = "config/.env.production\n"
    gi.write_text(initial_content)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    final_content = gi.read_text()
    expected_content = (
        "config/.env.production\n\n"
        "# prompttest cache\n.prompttest_cache/\n\n"
        "# Environment variables\n.env\n"
    )
    assert final_content == expected_content
    assert "(updated)" in result.stdout


def test_gitignore_preserves_crlf_line_endings_when_appending(
    runner, in_tmp_project: Path
):
    gi = in_tmp_project / ".gitignore"
    initial_content = b"node_modules/\r\n"
    gi.write_bytes(initial_content)

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    final_bytes = gi.read_bytes()

    assert final_bytes.startswith(initial_content)
    assert b"\r\n\r\n# prompttest cache\r\n.prompttest_cache/\r\n" in final_bytes
    assert b"\n" not in final_bytes.replace(b"\r\n", b"")


def test_gitignore_line_ending_probe_falls_back_on_exception(
    monkeypatch, runner, in_tmp_project: Path
):
    gi = in_tmp_project / ".gitignore"
    gi.write_text("prelude\n", encoding="utf-8")

    original_read_bytes = Path.read_bytes

    def fake_read_bytes(self: Path, *args, **kwargs):
        if self.name == ".gitignore":
            raise OSError("simulated read_bytes failure")
        return original_read_bytes(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    from prompttest.cli import app

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    expected = (
        "prelude\n\n"
        "# prompttest cache\n.prompttest_cache/\n\n"
        "# Environment variables\n.env\n"
    )
    assert gi.read_text(encoding="utf-8") == expected
    assert "(updated)" in result.stdout
