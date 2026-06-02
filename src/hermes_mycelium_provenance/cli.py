from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .git_ops import commits_between, current_head, show_note
from .model import SessionLedger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hermes-mycelium-provenance")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show local ledger status")
    audit = sub.add_parser("audit", help="audit notes for a repo against local ledgers")
    audit.add_argument("repo", nargs="?", default=".")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        return _status()
    if args.cmd == "audit":
        return _audit(Path(args.repo))
    return 2


def _load_ledgers(root: Path) -> list[SessionLedger]:
    sessions = root / "sessions"
    if not sessions.exists():
        return []
    out: list[SessionLedger] = []
    for path in sorted(sessions.glob("*.json")):
        try:
            out.append(SessionLedger.from_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _status() -> int:
    cfg = load_config()
    ledgers = _load_ledgers(cfg.ledger_root)
    repos = sorted({repo for ledger in ledgers for repo in ledger.repos})
    print(json.dumps({
        "ledger_root": str(cfg.ledger_root),
        "note_ref": cfg.note_ref,
        "sessions": len(ledgers),
        "repos": repos,
    }, indent=2))
    return 0


def _audit(repo: Path) -> int:
    cfg = load_config()
    repo = repo.resolve()
    ledgers = _load_ledgers(cfg.ledger_root)
    findings: list[dict[str, object]] = []
    for ledger in ledgers:
        record = ledger.repos.get(str(repo))
        if not record:
            continue
        final = current_head(repo)
        produced = record.produced_commits or commits_between(repo, record.initial_head, final)
        for commit in produced:
            note = show_note(repo, commit, cfg.note_ref)
            has_session = ledger.session_id in note
            findings.append({
                "session_id": ledger.session_id,
                "commit": commit,
                "has_note": has_session,
            })
    missing = [f for f in findings if not f["has_note"]]
    print(json.dumps({
        "repo": str(repo),
        "note_ref": cfg.note_ref,
        "checked": len(findings),
        "missing": missing,
        "ok": not missing,
    }, indent=2))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
