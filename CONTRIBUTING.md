# Contributing

Thanks for helping improve Hermes Mycelium Provenance.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python -m build
```

## Development workflow

1. **Open an issue first** for non-trivial changes so scope and approach can be discussed.
2. **Create a feature branch** from `main`.
3. **Write tests** for new behavior or bug fixes.
4. **Run the full local check suite:**
   ```bash
   ruff check .
   mypy src tests
   pytest
   python -m build
   ```
5. **Update docs** (`README.md`, `docs/`, or inline docstrings) if behavior changes.
6. **Open a pull request** using the provided template.

## Contribution scope

Welcome changes:

- safer note schemas and redaction behavior;
- compatibility fixes for Hermes plugin hooks;
- audit/reconcile improvements;
- tests around git-notes edge cases;
- docs that clarify safety boundaries.

Not currently planned:

- storing raw transcripts in notes;
- automatic public syncing of notes refs;
- replacing canonical issue/Kanban/PR state with git notes.

## Code style

- `ruff` enforces formatting and linting (`line-length = 100`).
- `mypy` checks types with `warn_unused_ignores` and `warn_redundant_casts`.
- Prefer explicit over implicit; avoid `Any` where a tighter type is practical.

## Testing

- `pytest` is the test runner.
- Tests live in `tests/` and should be deterministic and hermetic.
- Use temporary directories (`tmp_path`) instead of touching the real `~/.hermes`.

## Pull request checklist

- [ ] Tests pass locally (`pytest`).
- [ ] New behavior has tests.
- [ ] Lint and type checks pass (`ruff check .` and `mypy src tests`).
- [ ] Public docs do not include private paths, credentials, or raw transcripts.
- [ ] Safety/exportability implications are documented.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Do not file public issues for vulnerabilities.
