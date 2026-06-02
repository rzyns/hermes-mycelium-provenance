from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    enabled: bool = True
    ledger_root: Path = Path.home() / ".hermes" / "mycelium-provenance"
    note_ref: str = "refs/notes/mycelium"
    write_notes: bool = True
    inject_context: bool = True
    finalize_on_turn: bool = True
    max_paths_per_note: int = 25


def _truthy(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    return Config(
        enabled=_truthy(os.environ.get("HMP_ENABLED"), True),
        ledger_root=Path(os.environ.get("HMP_LEDGER_ROOT", str(Path.home() / ".hermes" / "mycelium-provenance"))).expanduser(),
        note_ref=os.environ.get("HMP_NOTES_REF", "refs/notes/mycelium"),
        write_notes=_truthy(os.environ.get("HMP_WRITE_NOTES"), True),
        inject_context=_truthy(os.environ.get("HMP_INJECT_CONTEXT"), True),
        finalize_on_turn=_truthy(os.environ.get("HMP_FINALIZE_ON_TURN"), True),
    )
