# Contributing

Thanks for helping improve Hermes Mycelium Provenance.

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
python -m build
```

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

## Pull request checklist

- [ ] Tests pass locally.
- [ ] New behavior has tests.
- [ ] Public docs do not include private paths, credentials, or raw transcripts.
- [ ] Safety/exportability implications are documented.
