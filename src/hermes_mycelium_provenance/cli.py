from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from .config import Config, load_config
from .git_ops import (
    GitError,
    commits_between,
    current_head,
    git_common_dir,
    show_note,
)
from .model import SessionLedger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-mycelium-provenance")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="show resolved config and ledger statistics")

    audit = sub.add_parser("audit", help="audit local ledgers against repo notes")
    audit.add_argument("repo", nargs="?", default=".")

    args = parser.parse_args(argv)
    if args.cmd == "status":
        return _status()
    if args.cmd == "audit":
        return _audit(Path(args.repo))
    return 2


def _load_ledgers(root: Path) -> tuple[list[SessionLedger], list[str]]:
    sessions = root / "sessions"
    if not sessions.exists():
        return [], []
    out: list[SessionLedger] = []
    errors: list[str] = []
    for path in sorted(sessions.glob("*.json")):
        try:
            out.append(SessionLedger.from_json(path.read_text(encoding="utf-8")))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    return out, errors


def _ledger_permissions(cfg: Config) -> dict[str, object]:
    def _mode(path: Path) -> str | None:
        try:
            return oct(path.stat().st_mode & 0o777)
        except OSError:
            return None

    out: dict[str, object] = {
        "ledger_root_exists": cfg.ledger_root.exists(),
        "ledger_root_writable": os.access(str(cfg.ledger_root), os.W_OK) if cfg.ledger_root.exists() else None,
    }
    if cfg.ledger_root.exists():
        out["ledger_root_mode"] = _mode(cfg.ledger_root)
        sessions_dir = cfg.ledger_root / "sessions"
        if sessions_dir.exists():
            out["sessions_dir_mode"] = _mode(sessions_dir)
    return out


def _status() -> int:
    cfg = load_config()
    ledgers, parse_errors = _load_ledgers(cfg.ledger_root)

    platforms = Counter[str]()
    models = Counter[str]()
    providers = Counter[str]()
    finalized = 0
    bootstrap = 0
    actionable = 0
    common_dirs_seen: set[str] = set()
    total_commits = 0
    total_notes_written = 0
    total_errors = 0

    for ledger in ledgers:
        if ledger.finalized_at:
            finalized += 1
        if not ledger.repos:
            bootstrap += 1
        else:
            actionable += 1
        if ledger.platform:
            platforms[ledger.platform] += 1
        if ledger.model:
            models[ledger.model] += 1
        if ledger.provider:
            providers[ledger.provider] += 1
        for repo_key, record in ledger.repos.items():
            common_dirs_seen.add(record.git_common_dir or repo_key)
            total_commits += len(record.produced_commits)
            total_notes_written += len(record.notes_written)
            total_errors += len(record.note_errors)

    note_write_ready = bool(
        cfg.write_notes
        and cfg.ledger_root.exists()
        and os.access(str(cfg.ledger_root), os.W_OK)
    )

    print(json.dumps({
        "config": {
            "ledger_root": str(cfg.ledger_root),
            "note_ref": cfg.note_ref,
            "write_notes": cfg.write_notes,
            "inject_context": cfg.inject_context,
            "finalize_on_turn": cfg.finalize_on_turn,
            "enabled": cfg.enabled,
        },
        "permissions": _ledger_permissions(cfg),
        "ledgers": {
            "total": len(ledgers),
            "finalized": finalized,
            "bootstrap": bootstrap,
            "actionable": actionable,
        },
        "counts": {
            "platforms": dict(platforms),
            "models": dict(models),
            "providers": dict(providers),
            "unique_repos": len(common_dirs_seen),
            "total_produced_commits": total_commits,
            "total_notes_written": total_notes_written,
            "total_note_errors": total_errors,
        },
        "note_write_ready": note_write_ready,
        "parse_errors": parse_errors,
    }, indent=2))
    return 0


def _audit(repo: Path) -> int:
    cfg = load_config()
    repo = repo.resolve()
    ledgers, parse_errors = _load_ledgers(cfg.ledger_root)

    findings: list[dict[str, object]] = []
    duplicate_candidates: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []

    # Resolve the common-dir for the target repo so worktree-path mismatches
    # do not hide records that actually belong to the same underlying repo.
    target_common = git_common_dir(repo) or str(repo)

    for ledger in ledgers:
        # Match on common-dir identity, not exact repo_root string.
        matching_record = None
        for repo_key, record in ledger.repos.items():
            record_common = record.git_common_dir or repo_key
            if record_common == target_common:
                matching_record = record
                break
        if not matching_record:
            continue
        final = current_head(repo)
        produced = matching_record.produced_commits or commits_between(repo, matching_record.initial_head, final)
        for commit in produced:
            try:
                note_text = show_note(repo, commit, cfg.note_ref)
            except GitError:
                note_text = ""
            has_session = ledger.session_id in note_text
            entry: dict[str, object] = {
                "session_id": ledger.session_id,
                "commit": commit,
                "has_note": has_session,
            }
            findings.append(entry)
            if not has_session:
                missing.append(entry)

    # Duplicate-attribution candidates: multiple ledgers claim the same commit
    # within the same common Git directory (i.e., same underlying repo).
    by_commit: dict[str, list[str]] = {}
    for f in findings:
        commit = str(f["commit"])
        session_id = str(f["session_id"])
        by_commit.setdefault(commit, []).append(session_id)
    for commit, sessions in by_commit.items():
        if len(sessions) > 1:
            duplicate_candidates.append({
                "commit": commit,
                "sessions": sessions,
            })

    print(json.dumps({
        "repo": str(repo),
        "note_ref": cfg.note_ref,
        "checked": len(findings),
        "missing": missing,
        "duplicate_candidates": duplicate_candidates,
        "parse_errors": parse_errors,
        "ok": not missing and not duplicate_candidates,
    }, indent=2))
    return 1 if missing or duplicate_candidates else 0
