# Security Policy

## Reporting a vulnerability

Please **do not file public issues** containing secrets, exploit payloads, or sensitive transcript content.

Until GitHub Security Advisories are enabled for the public repository, report suspected vulnerabilities privately to the maintainer through the repository owner's preferred private contact channel.

Include:
- a description of the issue and its impact;
- steps to reproduce (minimum viable example or commit range);
- affected versions or commit SHAs;
- suggested mitigation or patch, if any.

## Disclosure timeline

We aim to acknowledge receipt within 5 business days and provide an initial assessment within 10 business days. Coordinated disclosure timing will be agreed with the reporter before public fix release.

## Supported versions

This project is currently experimental alpha. Security fixes will target the latest unreleased/mainline code until versioned releases exist.

## Sensitive data posture

This plugin is designed **not** to write raw user messages, raw assistant responses, tokens, or full transcripts into git notes. Treat all generated notes as **public-for-safety** anyway, because notes refs can be synced or retained unexpectedly.

## Secret scanning

Before any push or publication, run a history-level secret scan:

```bash
python scripts/secret_scan.py
```

This checks the full git history for high-confidence secret patterns (API keys, tokens, passwords, private keys). If it reports matches, rotate the credential and rewrite history before publication.

## Scope

This security policy covers:
- the plugin source code (`src/`),
- test code (`tests/`),
- documentation that describes behavior (`README.md`, `docs/`),
- generated git notes and ledger files.

It does not cover:
- transient data produced by the Hermes agent itself outside this plugin,
- misconfiguration by the end user (such as enabling `write_notes` on a public repo without review).

## Incident response steps (template)

1. **Contain**: if a secret leaks, rotate it immediately.
2. **Assess**: determine which commits and branches contain the material.
3. **Remove**: rewrite history or use `git-filter-repo`/`BFG` to excise the secret.
4. **Verify**: re-run the secret scanner to confirm removal.
5. **Document**: record the incident and lessons learned in a private log.
