from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _run_git(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(["git", "init"], repo)
    _run_git(["git", "config", "user.email", "t@t.com"], repo)
    _run_git(["git", "config", "user.name", "T"], repo)
    return repo


def test_secret_scan_reports_src_when_same_secret_in_tests_and_src(
    temp_repo: Path,
) -> None:
    """Regression: scanner must flag src/ paths even if the same blob also
    appears under an allowed test path."""
    scanner = (Path(__file__).parent.parent / "scripts" / "secret_scan.py").resolve()
    fake_pat = "ghp_" + "x" * 36

    # Commit a test fixture with the fake secret.
    test_file = temp_repo / "tests" / "fixture.py"
    test_file.parent.mkdir()
    test_file.write_text(f"FAKE_KEY = '{fake_pat}'\n")
    _run_git(["git", "add", "."], temp_repo)
    _run_git(["git", "commit", "-m", "test fixture"], temp_repo)

    # Commit a source file with the SAME fake secret.
    src_file = temp_repo / "src" / "module.py"
    src_file.parent.mkdir()
    src_file.write_text(f"FAKE_KEY = '{fake_pat}'\n")
    _run_git(["git", "add", "."], temp_repo)
    _run_git(["git", "commit", "-m", "source module"], temp_repo)

    result = subprocess.run(
        [sys.executable, str(scanner)],
        cwd=temp_repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout
    assert "src/module.py" in result.stdout
    assert "tests/fixture.py" in result.stdout


def test_secret_scan_suppresses_when_secret_only_in_tests(temp_repo: Path) -> None:
    """Allowed paths should still suppress when the secret only appears there."""
    scanner = (Path(__file__).parent.parent / "scripts" / "secret_scan.py").resolve()
    fake_pat = "ghp_" + "x" * 36

    test_file = temp_repo / "tests" / "fixture.py"
    test_file.parent.mkdir()
    test_file.write_text(f"FAKE_KEY = '{fake_pat}'\n")
    _run_git(["git", "add", "."], temp_repo)
    _run_git(["git", "commit", "-m", "test fixture"], temp_repo)

    result = subprocess.run(
        [sys.executable, str(scanner)],
        cwd=temp_repo,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout
    assert "no high-confidence secrets" in result.stdout
