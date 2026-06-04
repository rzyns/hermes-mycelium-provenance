import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _active_hermes_home() -> Path | None:
    try:
        get_hermes_home = importlib.import_module("hermes_constants").get_hermes_home
        return get_hermes_home()
    except Exception:
        return None


def default_ledger_root() -> Path:
    """Return the active Hermes-home ledger root when Hermes exposes it."""
    hermes_home = _active_hermes_home()
    if hermes_home is not None:
        return hermes_home / "mycelium-provenance"
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


def _boolish(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return _truthy(value, default)
    return default


def _nonempty_str(value: Any, default: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return default


def _hermes_config_path() -> Path:
    hermes_home = _active_hermes_home()
    if hermes_home is not None:
        return hermes_home / "config.yaml"
    return Path.home() / ".hermes" / "config.yaml"


def _load_plugin_yaml_config() -> dict[str, Any]:
    """Read optional plugins.mycelium-provenance config from active Hermes home."""
    try:
        import yaml
    except Exception:
        return {}
    try:
        path = _hermes_config_path()
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    plugins = data.get("plugins")
    if isinstance(plugins, dict):
        raw = plugins.get("mycelium-provenance")
        return dict(raw) if isinstance(raw, dict) else {}
    if isinstance(plugins, list):
        for item in plugins:
            if isinstance(item, dict):
                raw = item.get("mycelium-provenance")
                if isinstance(raw, dict):
                    return dict(raw)
    return {}


def load_config() -> Config:
    file_config = _load_plugin_yaml_config()
    default_root = default_ledger_root()
    file_root = _nonempty_str(file_config.get("ledger_root"), str(default_root))
    file_note_ref = _nonempty_str(file_config.get("note_ref"), "refs/notes/mycelium")
    env_ledger_root = _nonempty_str(os.environ.get("HMP_LEDGER_ROOT"), file_root)
    env_note_ref = _nonempty_str(os.environ.get("HMP_NOTES_REF"), file_note_ref)
    return Config(
        enabled=_truthy(os.environ.get("HMP_ENABLED"), _boolish(file_config.get("enabled"), True)),
        ledger_root=Path(env_ledger_root).expanduser(),
        note_ref=env_note_ref,
        write_notes=_truthy(os.environ.get("HMP_WRITE_NOTES"), _boolish(file_config.get("write_notes"), False)),
        inject_context=_truthy(
            os.environ.get("HMP_INJECT_CONTEXT"), _boolish(file_config.get("inject_context"), False)
        ),
        finalize_on_turn=_truthy(
            os.environ.get("HMP_FINALIZE_ON_TURN"),
            _boolish(file_config.get("finalize_on_turn"), True),
        ),
    )
