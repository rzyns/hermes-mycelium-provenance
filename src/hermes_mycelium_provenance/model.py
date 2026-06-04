from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RepoRecord:
    repo_root: str
    initial_head: str | None = None
    final_head: str | None = None
    branch: str | None = None
    git_common_dir: str | None = None
    git_dir: str | None = None
    safe_remote_url: str | None = None
    touched_paths: list[str] = field(default_factory=list)
    git_commands: list[str] = field(default_factory=list)
    produced_commits: list[str] = field(default_factory=list)
    dirty_at_finalize: bool = False
    notes_written: list[str] = field(default_factory=list)
    note_errors: list[str] = field(default_factory=list)

    def add_path(self, path: str) -> None:
        if path and path not in self.touched_paths:
            self.touched_paths.append(path)

    def add_command(self, command: str) -> None:
        if command and command not in self.git_commands:
            self.git_commands.append(command)


@dataclass
class SessionLedger:
    schema_version: int
    session_id: str
    started_at: str
    profile: str | None = None
    platform: str | None = None
    model: str | None = None
    provider: str | None = None
    cwd: str = field(default_factory=lambda: str(Path.cwd()))
    user_message_hashes: list[str] = field(default_factory=list)
    assistant_response_hashes: list[str] = field(default_factory=list)
    repos: dict[str, RepoRecord] = field(default_factory=dict)
    finalized_at: str | None = None
    last_error: str | None = None

    def to_json(self) -> str:
        data = asdict(self)
        data["repos"] = {k: asdict(v) for k, v in self.repos.items()}
        return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> SessionLedger:
        raw = json.loads(text)
        repos = {k: RepoRecord(**v) for k, v in raw.pop("repos", {}).items()}
        ledger = cls(**raw)
        ledger.repos = repos
        return ledger


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def content_hash(value: Any) -> str:
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def default_profile_name() -> str | None:
    # Hermes does not currently pass profile name to plugin hooks. Prefer an
    # explicit env var when a runner sets one, otherwise keep the field absent.
    return os.environ.get("HERMES_PROFILE") or os.environ.get("HERMES_ACTIVE_PROFILE")


def ledger_path(root: Path, session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in session_id) or "unknown"
    return root / "sessions" / f"{safe}.json"
