from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def default_ledger_root() -> Path:
    """Return the active Hermes-home ledger root when Hermes exposes it."""
    try:
        from hermes_constants import get_hermes_home  # type: ignore[import-not-found]

        return get_hermes_home() / "mycelium-provenance"
    except Exception:
        return Path.home() / ".hermes" / "mycelium-provenance"


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    ledger_root: Path = field(default_factory=default_ledger_root)
    note_ref: str = "refs/notes/mycelium"
    write_notes: bool = False
    inject_context: bool = False
    finalize_on_turn: bool = True
    max_paths_per_note: int = 25


def _truthy(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    return Config(
        enabled=_truthy(os.environ.get("HMP_ENABLED"), True),
        ledger_root=Path(os.environ.get("HMP_LEDGER_ROOT", str(default_ledger_root()))).expanduser(),
        note_ref=os.environ.get("HMP_NOTES_REF", "refs/notes/mycelium"),
        write_notes=_truthy(os.environ.get("HMP_WRITE_NOTES"), False),
        inject_context=_truthy(os.environ.get("HMP_INJECT_CONTEXT"), False),
        finalize_on_turn=_truthy(os.environ.get("HMP_FINALIZE_ON_TURN"), True),
    )
