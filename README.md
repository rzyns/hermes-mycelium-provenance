# Hermes Mycelium Provenance

Hermes Mycelium Provenance is a Hermes Agent plugin that mechanically records repo-local agent-session provenance using Git notes / Mycelium-style refs.

It is designed for the gap between invisible chat transcripts and public code review: every meaningful agent-produced commit can carry a compact provenance envelope pointing back to the originating Hermes session ledger, without embedding the full private transcript in git history.

## Status

Experimental alpha. The plugin is local-first and fail-open by default. Do not sync `refs/notes/*` to public remotes until you have reviewed the generated notes and configured secret scanning for notes refs.

## What it does

- Observes Hermes lifecycle hooks: session start/finalize, tool calls, and turn completion.
- Detects git repositories touched by file and terminal tools.
- Maintains private local session ledgers under `~/.hermes/mycelium-provenance/`.
- Writes compact JSON provenance envelopes to `refs/notes/mycelium` for commits produced during a session.
- Injects existing HEAD notes as advisory context at the next turn, when enabled.
- Provides a small CLI for status and audit checks.

## What it deliberately does not do

- It does not store raw prompts, raw user messages, or full transcripts in git notes.
- It does not make Mycelium canonical task state. Use Kanban/issues/PRs/docs for canonical state.
- It does not automatically push notes refs.
- It does not claim notes are safe to publish without review.

## Installation for local development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

To use as a Hermes plugin from a checkout, install or symlink the repo into your Hermes plugin path according to your Hermes profile's plugin workflow, then enable the plugin in Hermes configuration.

A minimal Hermes plugin loader is provided at repository root:

```text
plugin.yaml
__init__.py
src/hermes_mycelium_provenance/
```

## Configuration

Environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `HMP_ENABLED` | `true` | Disable all behavior when false. |
| `HMP_LEDGER_ROOT` | `~/.hermes/mycelium-provenance` | Private local ledger root. |
| `HMP_NOTES_REF` | `refs/notes/mycelium` | Git notes ref to use. |
| `HMP_WRITE_NOTES` | `false` | Write commit notes on finalize. Keep disabled until you explicitly want the repo-local notes side effect. |
| `HMP_INJECT_CONTEXT` | `true` | Inject existing HEAD notes into future turns as advisory context. |
| `HMP_FINALIZE_ON_TURN` | `true` | Reconcile notes after each completed assistant turn. |

## CLI

```bash
hermes-mycelium-provenance status
hermes-mycelium-provenance audit /path/to/repo
```

`audit` exits non-zero if local ledgers identify produced commits whose note does not contain that session id.

## Note shape

Notes are compact JSON envelopes appended to `refs/notes/mycelium`:

```json
{
  "kind": "agent-session-origin",
  "session_id": "20260602_...",
  "repo": {
    "base_commit": "...",
    "produced_commit": "..."
  },
  "evidence": {
    "session_ledger": "~/.hermes/mycelium-provenance/sessions/...json",
    "user_message_hashes": ["sha256:..."]
  },
  "safety": {
    "contains_private_transcript": false,
    "exportable": false,
    "review_status": "draft"
  }
}
```

## Safety model

Treat notes as public-for-safety. Git hosting and secret scanners often ignore `refs/notes/*`; deleting a note does not necessarily erase it from notes-ref history. The plugin therefore stores only hashes and pointers by default, and marks notes `exportable: false` until reviewed.

## Development

```bash
pytest
python -m build
hermes-mycelium-provenance status
```

Before public publication, run a pre-publication audit including tracked files, git history, and package contents.
