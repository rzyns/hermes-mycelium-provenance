# Design: session provenance as repo-local breadcrumbs

This plugin treats Git notes / Mycelium as an object-adjacent breadcrumb layer, not as canonical memory.

Canonical routing remains:

- full transcripts: Hermes session storage / observability substrate;
- task state and gates: Kanban, issues, PRs;
- stable contributor instructions: repo docs and `AGENTS.md`;
- reusable procedures: Hermes skills;
- repo-local session provenance: `refs/notes/mycelium` compact envelopes.

The plugin is intentionally fail-open. If note writing fails, the session should continue; the ledger records the error and `audit` can detect drift later.
