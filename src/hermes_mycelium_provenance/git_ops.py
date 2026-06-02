from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Iterable
from pathlib import Path


class GitError(RuntimeError):
    """Raised for git operations that fail in a controlled way."""


def run_git(repo: Path, args: Iterable[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-C", str(repo), *args]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if check and proc.returncode != 0:
        raise GitError(proc.stderr.strip() or proc.stdout.strip() or f"git failed: {' '.join(cmd)}")
    return proc


def discover_repo(path: str | os.PathLike[str] | None) -> Path | None:
    """Return the containing git worktree root for *path*, or None."""
    if not path:
        candidate = Path.cwd()
    else:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = (Path.cwd() / candidate).resolve()
        if candidate.exists() and candidate.is_file() or not candidate.exists() and candidate.suffix:
            candidate = candidate.parent
    try:
        proc = subprocess.run(
            ["git", "-C", str(candidate), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return Path(root).resolve() if root else None


def current_head(repo: Path) -> str | None:
    proc = run_git(repo, ["rev-parse", "--verify", "HEAD"], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def branch_name(repo: Path) -> str | None:
    proc = run_git(repo, ["branch", "--show-current"], check=False)
    value = proc.stdout.strip() if proc.returncode == 0 else ""
    if value:
        return value
    proc = run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    value = proc.stdout.strip() if proc.returncode == 0 else ""
    return value if value and value != "HEAD" else None


def commits_between(repo: Path, old_head: str | None, new_head: str | None) -> list[str]:
    if not new_head:
        return []
    if old_head and old_head != new_head:
        spec = f"{old_head}..{new_head}"
        proc = run_git(repo, ["rev-list", "--reverse", spec], check=False)
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    # A repo created from scratch during the session can have no old HEAD.
    if old_head is None:
        proc = run_git(repo, ["rev-list", "--reverse", new_head], check=False)
        if proc.returncode == 0:
            return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    return []


def has_dirty_worktree(repo: Path) -> bool:
    proc = run_git(repo, ["status", "--porcelain"], check=False)
    return bool(proc.stdout.strip()) if proc.returncode == 0 else False


def note_ref_arg(note_ref: str) -> str:
    return f"--ref={note_ref}"


def show_note(repo: Path, commit: str, note_ref: str) -> str:
    proc = run_git(repo, ["notes", note_ref_arg(note_ref), "show", commit], check=False)
    return proc.stdout if proc.returncode == 0 else ""


def append_note(repo: Path, commit: str, note_ref: str, body: str) -> bool:
    existing = show_note(repo, commit, note_ref)
    marker = _session_marker_from_body(body)
    if marker and marker in existing:
        return False
    run_git(repo, ["notes", note_ref_arg(note_ref), "append", "-m", body, commit], check=True)
    return True


def _session_marker_from_body(body: str) -> str | None:
    # The note body is JSON. A substring marker is enough to avoid duplicate
    # appends without parsing arbitrary existing notes.
    for line in body.splitlines():
        if '"session_id"' in line:
            return line.strip().rstrip(",")
    return None


def parse_git_c_workdir(command: str) -> str | None:
    """Extract a best-effort path from `git -C <path> ...` terminal commands."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    if not parts or parts[0] != "git":
        return None
    for i, part in enumerate(parts[:-1]):
        if part == "-C":
            return parts[i + 1]
        if part.startswith("-C") and len(part) > 2:
            return part[2:]
    return None
