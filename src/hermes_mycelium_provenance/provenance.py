from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .git_ops import (
    append_note,
    branch_name,
    commits_between,
    current_head,
    discover_repo,
    has_dirty_worktree,
    parse_git_c_workdir,
    show_note,
)
from .model import (
    RepoRecord,
    SessionLedger,
    content_hash,
    default_profile_name,
    ledger_path,
    utc_now,
)

logger = logging.getLogger(__name__)

_PATH_ARG_KEYS = ("path", "file_path", "workdir", "cwd")
_WRITE_TOOLS = {"write_file", "patch", "skill_manage"}
_READ_TOOLS = {"read_file", "search_files"}
_GITISH_TOOLS = {"terminal"}


class ProvenanceState:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or load_config()
        self._sessions: dict[str, SessionLedger] = {}

    def on_session_start(
        self,
        *,
        session_id: str = "",
        platform: str = "",
        model: str = "",
        provider: str = "",
        **_: Any,
    ) -> None:
        if not self.config.enabled or not session_id:
            return
        ledger = self._sessions.get(session_id) or self._load_or_new(session_id)
        ledger.platform = platform or ledger.platform
        ledger.model = model or ledger.model
        ledger.provider = provider or ledger.provider
        ledger.profile = default_profile_name() or ledger.profile
        self._sessions[session_id] = ledger
        self._save(ledger)

    def pre_llm_call(self, *, session_id: str = "", **_: Any) -> dict[str, str] | None:
        if not self.config.enabled or not self.config.inject_context:
            return None
        repo = discover_repo(Path.cwd())
        if repo is None:
            return None
        head = current_head(repo)
        if not head:
            return None
        note = show_note(repo, head, self.config.note_ref).strip()
        if not note:
            return None
        excerpt = note[:1800]
        return {
            "context": (
                "Repo-local Mycelium/git-notes provenance is attached to the current HEAD. "
                "Use it as advisory breadcrumb context, not as canonical task state.\n\n"
                f"```json\n{excerpt}\n```"
            )
        }

    def pre_tool_call(self, *, tool_name: str = "", args: Any = None, session_id: str = "", **_: Any) -> None:
        if not self.config.enabled or not session_id:
            return
        # Observe before a terminal command in case it creates the first commit.
        self._observe_tool(tool_name, args, session_id)
        return None

    def post_tool_call(
        self,
        *,
        tool_name: str = "",
        args: Any = None,
        result: Any = None,
        session_id: str = "",
        **_: Any,
    ) -> None:
        if not self.config.enabled or not session_id:
            return
        self._observe_tool(tool_name, args, session_id)
        ledger = self._sessions.get(session_id)
        if ledger:
            self._save(ledger)
        return None

    def post_llm_call(
        self,
        *,
        session_id: str = "",
        user_message: Any = None,
        assistant_response: Any = None,
        platform: str = "",
        model: str = "",
        **_: Any,
    ) -> None:
        if not self.config.enabled or not session_id:
            return
        ledger = self._sessions.get(session_id) or self._load_or_new(session_id)
        if platform:
            ledger.platform = platform
        if model:
            ledger.model = model
        if user_message is not None:
            h = content_hash(user_message)
            if h not in ledger.user_message_hashes:
                ledger.user_message_hashes.append(h)
        if assistant_response is not None:
            h = content_hash(assistant_response)
            if h not in ledger.assistant_response_hashes:
                ledger.assistant_response_hashes.append(h)
        self._sessions[session_id] = ledger
        if self.config.finalize_on_turn:
            self.finalize(session_id=session_id, platform=platform)
        else:
            self._save(ledger)

    def finalize(self, *, session_id: str = "", platform: str = "", **_: Any) -> None:
        if not self.config.enabled or not session_id:
            return
        ledger = self._sessions.get(session_id) or self._load_or_new(session_id)
        if platform:
            ledger.platform = platform
        for repo_key, record in list(ledger.repos.items()):
            repo = Path(repo_key)
            try:
                final_head = current_head(repo)
                record.final_head = final_head
                record.branch = branch_name(repo) or record.branch
                record.dirty_at_finalize = has_dirty_worktree(repo)
                record.produced_commits = commits_between(repo, record.initial_head, final_head)
                if self.config.write_notes:
                    for commit in record.produced_commits:
                        body = self._note_body(ledger, record, commit)
                        if append_note(repo, commit, self.config.note_ref, body):
                            record.notes_written.append(commit)
            except Exception as exc:  # fail-open: audit can repair later
                message = f"{repo}: {exc}"
                logger.warning("mycelium-provenance finalize failed: %s", message)
                record.note_errors.append(message)
                ledger.last_error = message
        ledger.finalized_at = utc_now()
        self._save(ledger)

    def _observe_tool(self, tool_name: str, args: Any, session_id: str) -> None:
        if not isinstance(args, dict):
            args = {}
        paths = self._candidate_paths(tool_name, args)
        if not paths:
            return
        ledger = self._sessions.get(session_id) or self._load_or_new(session_id)
        for path in paths:
            repo = discover_repo(path)
            if repo is None:
                continue
            record = ledger.repos.get(str(repo))
            if record is None:
                record = RepoRecord(repo_root=str(repo), initial_head=current_head(repo), branch=branch_name(repo))
                ledger.repos[str(repo)] = record
            if tool_name in _WRITE_TOOLS | _READ_TOOLS:
                maybe_path = args.get("path") or args.get("file_path")
                if isinstance(maybe_path, str):
                    record.add_path(_relative_or_raw(repo, maybe_path))
            if tool_name in _GITISH_TOOLS:
                command = args.get("command")
                if isinstance(command, str) and "git" in command:
                    record.add_command(command[:500])
        self._sessions[session_id] = ledger

    def _candidate_paths(self, tool_name: str, args: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for key in _PATH_ARG_KEYS:
            value = args.get(key)
            if isinstance(value, str) and value:
                out.append(value)
        if tool_name == "terminal":
            command = args.get("command")
            workdir = args.get("workdir") or args.get("cwd")
            if isinstance(command, str):
                git_c = parse_git_c_workdir(command)
                if git_c:
                    if workdir and not Path(git_c).is_absolute():
                        out.append(str(Path(str(workdir)) / git_c))
                    else:
                        out.append(git_c)
            if not out and isinstance(command, str) and "git" in command:
                out.append(str(Path.cwd()))
        return out

    def _note_body(self, ledger: SessionLedger, record: RepoRecord, commit: str) -> str:
        note = {
            "kind": "agent-session-origin",
            "schema_version": 1,
            "session_id": ledger.session_id,
            "agent": {
                "profile": ledger.profile,
                "platform": ledger.platform,
                "model": ledger.model,
                "provider": ledger.provider,
            },
            "repo": {
                "root_name": Path(record.repo_root).name,
                "branch": record.branch,
                "base_commit": record.initial_head,
                "produced_commit": commit,
                "dirty_at_finalize": record.dirty_at_finalize,
            },
            "touched_paths": record.touched_paths[: self.config.max_paths_per_note],
            "git_commands_observed": len(record.git_commands),
            "evidence": {
                "session_ledger": str(ledger_path(self.config.ledger_root, ledger.session_id)),
                "user_message_hashes": ledger.user_message_hashes,
                "assistant_response_hashes": ledger.assistant_response_hashes,
            },
            "safety": {
                "contains_private_transcript": False,
                "exportable": False,
                "review_status": "draft",
            },
        }
        return json.dumps(note, indent=2, sort_keys=True, ensure_ascii=False)

    def _load_or_new(self, session_id: str) -> SessionLedger:
        path = ledger_path(self.config.ledger_root, session_id)
        if path.exists():
            try:
                return SessionLedger.from_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("mycelium-provenance could not load ledger %s: %s", path, exc)
        return SessionLedger(
            schema_version=1,
            session_id=session_id,
            started_at=utc_now(),
            profile=default_profile_name(),
            cwd=os.getcwd(),
        )

    def _save(self, ledger: SessionLedger) -> None:
        path = ledger_path(self.config.ledger_root, ledger.session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(ledger.to_json(), encoding="utf-8")
        tmp.replace(path)


def _relative_or_raw(repo: Path, maybe_path: str) -> str:
    p = Path(maybe_path).expanduser()
    if not p.is_absolute():
        p = (Path.cwd() / p).resolve()
    try:
        return str(p.resolve().relative_to(repo.resolve()))
    except Exception:
        return maybe_path
