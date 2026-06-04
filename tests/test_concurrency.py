from __future__ import annotations

import json
import multiprocessing
import threading
from pathlib import Path

import pytest

from hermes_mycelium_provenance.config import Config
from hermes_mycelium_provenance.model import SessionLedger, ledger_path, utc_now
from hermes_mycelium_provenance.provenance import ProvenanceState


def _mp_worker_run(args: tuple[Path, str, int]) -> bool:
    """Top-level helper so it can be pickled across processes.

    Args:
        args: (ledger_root, session_id, iterations_per_worker)
    """
    ledger_root, session_id, iterations = args
    state = ProvenanceState(Config(ledger_root=ledger_root, enabled=True))
    ledger = SessionLedger(
        schema_version=1,
        session_id=session_id,
        started_at=utc_now(),
    )
    local_ok = True
    for _ in range(iterations):
        ok = state._save(ledger)
        if not ok:
            local_ok = False
    return local_ok


def _run_concurrent_writes(
    ledger_root: Path,
    session_id: str,
    worker_count: int,
    iterations_per_worker: int,
    worker_kind: str,
) -> list[bool]:
    """Spawn workers that all save the same ledger concurrently.

    Returns a list of success booleans from each worker's perspective.
    """
    state = ProvenanceState(Config(ledger_root=ledger_root, enabled=True))
    ledger = SessionLedger(
        schema_version=1,
        session_id=session_id,
        started_at=utc_now(),
    )

    successes: list[bool] = []
    lock = threading.Lock()

    def thread_worker() -> None:
        local_ok = True
        for _ in range(iterations_per_worker):
            ok = state._save(ledger)
            if not ok:
                local_ok = False
        with lock:
            successes.append(local_ok)

    if worker_kind == "thread":
        threads = [threading.Thread(target=thread_worker) for _ in range(worker_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    elif worker_kind == "process":
        with multiprocessing.Pool(worker_count) as pool:
            args = (ledger_root, session_id, iterations_per_worker)
            results = pool.map(_mp_worker_run, [args] * worker_count)
            successes.extend(results)
    else:
        raise ValueError(worker_kind)

    return successes


@pytest.mark.parametrize("worker_kind", ["thread", "process"])
def test_concurrent_saves_no_race(tmp_path: Path, worker_kind: str) -> None:
    ledger_root = tmp_path / "ledger"
    session_id = "sess-concurrent"

    successes = _run_concurrent_writes(
        ledger_root=ledger_root,
        session_id=session_id,
        worker_count=8,
        iterations_per_worker=50,
        worker_kind=worker_kind,
    )

    # Every worker should report success.
    assert all(successes), f"Some workers failed: {successes}"

    # The final file must exist and be valid JSON.
    path = ledger_path(ledger_root, session_id)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["session_id"] == session_id
    assert data["schema_version"] == 1

    # Permissions must remain strict.
    assert oct(ledger_root.stat().st_mode & 0o777) == "0o700"
    assert oct((ledger_root / "sessions").stat().st_mode & 0o777) == "0o700"
    assert oct(path.stat().st_mode & 0o777) == "0o600"

    # There must be zero leftover temp files.
    parent = path.parent
    assert list(parent.glob(".*.tmp*")) == []


def test_no_orphan_tmp_after_failed_save(tmp_path: Path) -> None:
    """Ensure the cleanup path removes the temp file on write failure."""
    ledger_root = tmp_path / "ledger"
    session_id = "sess-orphan"

    state = ProvenanceState(Config(ledger_root=ledger_root, enabled=True))
    ledger = SessionLedger(
        schema_version=1,
        session_id=session_id,
        started_at=utc_now(),
    )

    # Induce a failure by mocking to_json to raise.
    class BadLedger(SessionLedger):
        def to_json(self) -> str:
            raise RuntimeError("injected failure")

    bad = BadLedger(
        schema_version=ledger.schema_version,
        session_id=ledger.session_id,
        started_at=ledger.started_at,
    )
    ok = state._save(bad)
    assert not ok

    parent = ledger_path(ledger_root, session_id).parent
    assert list(parent.glob(".*.tmp*")) == []

    # Normal save still works afterwards.
    ok2 = state._save(ledger)
    assert ok2
    path = ledger_path(ledger_root, session_id)
    assert path.exists()
