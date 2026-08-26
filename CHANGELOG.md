# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## [Unreleased]

## [0.1.1] - 2026-08-26

Public-health and publication-hygiene release. These changes were reviewed and approved before
`0.1.0` was tagged, but were never merged into `main`, so they did not ship in that release.

### Added

- `scripts/secret_scan.py`: history-level scan for high-confidence secret patterns (API keys,
  tokens, passwords, private keys), plus `tests/test_secret_scan.py`.
- CI now runs the secret scan on pull requests and pushes to `main`.

### Changed

- `SECURITY.md`: names a concrete private reporting route instead of referring vaguely to the
  maintainer's "preferred private contact channel", and documents a capacity-qualified disclosure
  timeline, sensitive-data posture, secret-scanning procedure, scope, and incident-response steps.
- `CODE_OF_CONDUCT.md`: names a concrete private enforcement contact.
- `CONTRIBUTING.md`: expanded contributor guidance.

## [0.1.0] - 2026-06-09

Initial public release.

### Added

- Initial Hermes plugin hooks for session provenance collection.
- Local session ledger under `~/.hermes/mycelium-provenance`.
- Git notes writer for `refs/notes/mycelium`.
- Advisory pre-LLM context injection from current HEAD notes.
- `status` and `audit` CLI commands.

[Unreleased]: https://github.com/hermegeddon/hermes-mycelium-provenance/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/hermegeddon/hermes-mycelium-provenance/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/hermegeddon/hermes-mycelium-provenance/releases/tag/v0.1.0
