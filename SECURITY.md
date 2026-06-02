# Security Policy

## Reporting a vulnerability

Please do not file public issues containing secrets, exploit payloads, or sensitive transcript content.

Until GitHub Security Advisories are enabled for the public repository, report suspected vulnerabilities privately to the maintainer through the repository owner's preferred private contact channel.

## Supported versions

This project is currently experimental alpha. Security fixes will target the latest unreleased/mainline code until versioned releases exist.

## Sensitive data posture

This plugin is designed not to write raw user messages, raw assistant responses, tokens, or full transcripts into git notes. Treat all generated notes as public-for-safety anyway, because notes refs can be synced or retained unexpectedly.
