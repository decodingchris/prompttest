from __future__ import annotations

from pathlib import Path

from prompttest.cli import app


# --- Integration: a realistic first-time user journey ---


def test_full_user_journey_init_then_run(runner, in_tmp_project: Path):
    # 1) Developer runs "prompttest init"
    init_result = runner.invoke(app, ["init"])
    assert init_result.exit_code == 0
    out = init_result.stdout

    # Validate highlighted onboarding content
    assert "Successfully initialized prompttest!" in out
    assert "Open the .env file" in out
    assert "OPENROUTER_API_KEY=" in out
    assert "GUIDE.md" in out
    assert "Run `prompttest` to see your example tests run!" in out

    # Validate project structure exists
    assert (in_tmp_project / "prompts" / "customer_service.txt").exists()
    assert (in_tmp_project / "prompttests" / "prompttest.yml").exists()
    assert (in_tmp_project / "prompttests" / "main.yml").exists()
    assert (in_tmp_project / "prompttests" / "GUIDE.md").exists()
    assert (in_tmp_project / ".env").exists()
    assert (in_tmp_project / ".env.example").exists()
    assert (in_tmp_project / ".gitignore").exists()

    # 2) Developer then runs "prompttest" (no args) and sees the default run command
    run_result = runner.invoke(app, [])
    assert run_result.exit_code == 0
    assert "TODO: Implement the run command." in run_result.stdout


def test_re_running_init_shows_skipped_statuses_and_preserves_content(
    runner, in_tmp_project: Path
):
    # Initialize once
    first = runner.invoke(app, ["init"])
    assert first.exit_code == 0

    # Capture a couple of file contents
    env_before = (in_tmp_project / ".env").read_text()
    prompt_before = (in_tmp_project / "prompts" / "customer_service.txt").read_text()

    # Initialize again
    second = runner.invoke(app, ["init"])
    assert second.exit_code == 0

    # Statuses indicate skipping
    out = second.stdout
    assert out.count("(exists, skipped)") >= 6
    assert ".gitignore" in out and "(exists, skipped)" in out

    # Contents preserved exactly
    assert (in_tmp_project / ".env").read_text() == env_before
    assert (
        in_tmp_project / "prompts" / "customer_service.txt"
    ).read_text() == prompt_before
