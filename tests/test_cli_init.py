from __future__ import annotations

from pathlib import Path


from prompttest.cli import app


# --- Core Value: Safe scaffolding with clear UX, idempotency, and exact content ---


def test_init_creates_expected_files_with_exact_content_and_summary(
    runner, in_tmp_project: Path, template_texts
):
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0

    # Verify created files exist with exact contents
    for rel_path, expected in template_texts.items():
        p = in_tmp_project / rel_path
        assert p.exists(), f"Expected {rel_path} to be created"
        assert p.read_text() == expected, f"Unexpected content in {rel_path}"

    # Verify .gitignore created exactly with expected content
    gitignore_path = in_tmp_project / ".gitignore"
    assert gitignore_path.exists()
    assert (
        gitignore_path.read_text()
        == "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n"
    )

    # Validate key parts of the output UX
    out = result.stdout
    assert "Initializing prompttest project" in out
    assert "Successfully initialized prompttest!" in out
    assert "Project structure:" in out
    assert "prompts/customer_service.txt" in out
    assert "prompttests/prompttest.yml" in out
    assert "prompttests/main.yml" in out
    assert "prompttests/GUIDE.md" in out
    assert ".env" in out and "DO NOT COMMIT" in out
    # .gitignore should show created status on first init
    assert ".gitignore" in out and "(created)" in out
    # "Next steps" guide is printed
    assert "Next steps:" in out
    assert "OpenRouter" in out
    assert "API Key Setup" in out
    assert "Run `prompttest` to see your example tests run!" in out
    assert "Happy testing" in out


def test_init_is_idempotent_and_does_not_overwrite_existing_files(
    runner, in_tmp_project: Path, template_texts
):
    # First run creates everything
    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0

    # Capture contents after first run
    before_contents = {
        rel: (in_tmp_project / rel).read_text() for rel in template_texts
    }

    # Second run should not overwrite; statuses should show skipped
    second = runner.invoke(app, ["init"])
    assert second.exit_code == 0

    # Verify contents are unchanged
    for rel_path, before in before_contents.items():
        after = (in_tmp_project / rel_path).read_text()
        assert after == before, f"File was overwritten unexpectedly: {rel_path}"

    # .gitignore should not change on second run
    gitignore = (in_tmp_project / ".gitignore").read_text()
    assert (
        gitignore
        == "# prompttest cache\n.prompttest_cache/\n\n# Environment variables\n.env\n"
    )

    # Output should reflect idempotency for files and .gitignore
    out = second.stdout
    # All files reported as (exists, skipped)
    assert out.count("(exists, skipped)") >= 6, (
        "Expected skipped statuses for scaffolded files"
    )
    # .gitignore reported as skipped
    assert ".gitignore" in out and "(exists, skipped)" in out
