from __future__ import annotations

import json
import subprocess
from pathlib import Path

from hermes_mycelium_provenance.cli import main
from hermes_mycelium_provenance.config import Config
from hermes_mycelium_provenance.provenance import ProvenanceState


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=True)
    return proc.stdout.strip()


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.name", "Test User")
    git(repo, "config", "user.email", "test@example.invalid")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    return repo


def test_status_shows_config_and_counts(monkeypatch, tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    state = ProvenanceState(Config(ledger_root=ledger_root, enabled=True))
    state.on_session_start(session_id="sess-a", platform="discord", model="m1", provider="ollama")
    state.on_session_start(session_id="sess-b", platform="cli", model="m2")
    state.finalize(session_id="sess-a", platform="discord")

    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))
    monkeypatch.setenv("HMP_WRITE_NOTES", "true")

    out = json.loads(_capture_stdout(main, ["status"]))

    assert out["config"]["ledger_root"] == str(ledger_root)
    assert out["config"]["write_notes"] is True
    assert out["ledgers"]["total"] == 2
    assert out["ledgers"]["finalized"] == 1
    assert out["counts"]["platforms"]["discord"] == 1
    assert out["counts"]["platforms"]["cli"] == 1
    assert out["counts"]["models"]["m1"] == 1
    assert out["counts"]["models"]["m2"] == 1
    assert out["counts"]["providers"]["ollama"] == 1
    assert out["note_write_ready"] is True
    assert "permissions" in out


def test_status_reports_parse_errors(monkeypatch, tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    (ledger_root / "sessions").mkdir(parents=True)
    (ledger_root / "sessions" / "bad.json").write_text("not json", encoding="utf-8")

    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))

    out = json.loads(_capture_stdout(main, ["status"]))
    assert len(out["parse_errors"]) == 1
    assert "bad.json" in out["parse_errors"][0]


def test_audit_ok_when_notes_present(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    ledger_root = tmp_path / "ledger"
    state = ProvenanceState(Config(ledger_root=ledger_root, write_notes=True, finalize_on_turn=False))
    state.on_session_start(session_id="sess-ok")
    state.post_tool_call(
        session_id="sess-ok",
        tool_name="write_file",
        args={"path": str(repo / "a.py"), "content": "a=1\n"},
        result="{}",
    )
    (repo / "a.py").write_text("a=1\n", encoding="utf-8")
    git(repo, "add", "a.py")
    git(repo, "commit", "-m", "add a")
    state.finalize(session_id="sess-ok")

    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))

    out = json.loads(_capture_stdout(main, ["audit", str(repo)]))
    assert out["checked"] == 1
    assert out["missing"] == []
    assert out["duplicate_candidates"] == []
    assert out["ok"] is True


def test_audit_finds_missing_notes(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    ledger_root = tmp_path / "ledger"
    state = ProvenanceState(Config(ledger_root=ledger_root, write_notes=False, finalize_on_turn=False))
    state.on_session_start(session_id="sess-miss")
    state.post_tool_call(
        session_id="sess-miss",
        tool_name="write_file",
        args={"path": str(repo / "a.py"), "content": "a=1\n"},
        result="{}",
    )
    (repo / "a.py").write_text("a=1\n", encoding="utf-8")
    git(repo, "add", "a.py")
    git(repo, "commit", "-m", "add a")
    state.finalize(session_id="sess-miss")

    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))

    out = json.loads(_capture_stdout(main, ["audit", str(repo)]))
    assert out["checked"] == 1
    assert len(out["missing"]) == 1
    assert out["missing"][0]["session_id"] == "sess-miss"
    assert out["ok"] is False


def test_audit_finds_duplicate_candidates(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    ledger_root = tmp_path / "ledger"

    state1 = ProvenanceState(Config(ledger_root=ledger_root, write_notes=False, finalize_on_turn=False))
    state1.on_session_start(session_id="sess-dup-1")
    state1.post_tool_call(
        session_id="sess-dup-1",
        tool_name="write_file",
        args={"path": str(repo / "a.py"), "content": "a=1\n"},
        result="{}",
    )

    state2 = ProvenanceState(Config(ledger_root=ledger_root, write_notes=False, finalize_on_turn=False))
    state2.on_session_start(session_id="sess-dup-2")
    state2.post_tool_call(
        session_id="sess-dup-2",
        tool_name="write_file",
        args={"path": str(repo / "b.py"), "content": "b=2\n"},
        result="{}",
    )

    # Single commit after both sessions started: both claim it.
    (repo / "c.py").write_text("c=3\n", encoding="utf-8")
    git(repo, "add", "c.py")
    git(repo, "commit", "-m", "add c")

    state1.finalize(session_id="sess-dup-1")
    state2.finalize(session_id="sess-dup-2")

    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))

    out = json.loads(_capture_stdout(main, ["audit", str(repo)]))
    assert len(out["duplicate_candidates"]) == 1
    assert sorted(out["duplicate_candidates"][0]["sessions"]) == ["sess-dup-1", "sess-dup-2"]
    assert out["ok"] is False


def test_audit_handles_git_error_gracefully(monkeypatch, tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    (ledger_root / "sessions").mkdir(parents=True)
    # No repo; .resolve() will be used but audit should handle missing git gracefully
    monkeypatch.setenv("HMP_LEDGER_ROOT", str(ledger_root))

    # No ledgers referencing a repo = empty audit
    out = json.loads(_capture_stdout(main, ["audit", str(tmp_path)]))
    assert out["checked"] == 0
    assert out["missing"] == []
    assert out["duplicate_candidates"] == []
    assert out["ok"] is True


def _capture_stdout(fn, args: list[str]) -> str:
    import io
    import sys
    old = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    try:
        fn(args)
    except SystemExit as exc:
        if exc.code not in (0, None):
            raise
    finally:
        sys.stdout = old
    return buf.getvalue()
