#!/usr/bin/env python3
"""History-level secret scan for hermes-mycelium-provenance.

Checks full git history for high-confidence secret patterns.
Exit 0 if nothing suspicious found; exit 1 and print matches otherwise.

Usage:
    python scripts/secret_scan.py [--verbose]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Patterns are tuned for high-confidence matches on common secret types.
# They intentionally avoid low-confidence heuristics that produce false positives.
PATTERNS: dict[str, re.Pattern] = {
    # OpenAI/Anthropic/HuggingFace style API key
    "api_key": re.compile(
        r"\b(?:sk|hf)-(?:[a-zA-Z0-9]{20,}|[a-zA-Z0-9_-]{20,})\b"
    ),
    # AWS access key id
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # Generic private key block
    "private_key": re.compile(
        r"-----BEGIN (?:OPENSSH |RSA |DSA |EC |PGP |)?PRIVATE KEY-----"
    ),
    # GitHub personal access token (classic or fine-grained prefix)
    "github_token": re.compile(
        r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"
    ),
    # Generic password= or passwd= with likely value
    "password_assignment": re.compile(
        r"(?i)(?:password|passwd|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"
    ),
    # Slack / Discord webhook URL
    "webhook_url": re.compile(
        r"https?://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+"
    ),
    "discord_webhook": re.compile(
        r"https?://discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]+"
    ),
    # Generic bearer token in header-like string
    "bearer_token": re.compile(
        r"(?i)bearer\s+[a-z0-9_\-\.]{20,}"
    ),
    # JWT-like token (three base64url segments)
    "jwt": re.compile(
        r"\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]+\b"
    ),
}

# Paths that are allowed to contain patterns (e.g., test fixtures that are
# intentionally fake or redacted examples).
ALLOWED_PATHS: list[str] = [
    "tests/",
]


def git_all_objects() -> list[str]:
    """Return a list of all blob SHAs in the repo history."""
    result = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        capture_output=True,
        text=True,
        check=True,
    )
    blobs: list[str] = []
    seen: set[str] = set()
    for line in result.stdout.strip().splitlines():
        parts = line.split(maxsplit=1)
        if not parts:
            continue
        sha = parts[0]
        if sha in seen:
            continue
        seen.add(sha)
        # check if this is a blob
        t = subprocess.run(
            ["git", "cat-file", "-t", sha],
            capture_output=True,
            text=True,
            check=True,
        )
        if t.stdout.strip() == "blob":
            blobs.append(sha)
    return blobs


def blob_text(sha: str) -> str:
    """Return the text content of a git blob, decoding with replacement."""
    result = subprocess.run(
        ["git", "cat-file", "blob", sha],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace")


def path_is_allowed(path: str | None) -> bool:
    if not path:
        return False
    return any(path.startswith(prefix) for prefix in ALLOWED_PATHS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Git history secret scanner")
    parser.add_argument("--verbose", action="store_true", help="Show every scanned object")
    args = parser.parse_args()

    repo_root = Path.cwd()
    if not (repo_root / ".git").exists() and not (repo_root / ".git").is_file():
        print("Error: not inside a git repository.", file=sys.stderr)
        return 2

    blobs = git_all_objects()
    verbose = args.verbose

    findings: list[dict] = []
    for sha in blobs:
        try:
            content = blob_text(sha)
        except subprocess.CalledProcessError:
            continue

        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                matched_text = match.group(0)
                # Suppress very short matches that are likely false positives.
                if len(matched_text) < 16:
                    continue
                # Find which file paths in history point to this blob so the
                # user knows where to look.
                paths_result = subprocess.run(
                    ["git", "log", "--all", "--pretty=format:", "--name-only", "--diff-filter=A", "-S", matched_text],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                paths = sorted({
                    p.strip() for p in paths_result.stdout.strip().splitlines() if p.strip()
                })
                if any(path_is_allowed(p) for p in paths):
                    continue
                findings.append(
                    {
                        "sha": sha,
                        "kind": kind,
                        "match": matched_text,
                        "paths": paths,
                    }
                )
                if verbose:
                    print(f"  {sha[:12]} {kind}: {matched_text[:60]}")

    if findings:
        print(f"Secret scan: {len(findings)} finding(s) detected.")
        for f in findings:
            paths_str = ", ".join(f["paths"]) if f["paths"] else "unknown"
            print(f"  [{f['kind']}] {f['sha'][:12]} in {paths_str}")
            print(f"    match: {f['match'][:120]}")
        return 1

    print(f"Secret scan: no high-confidence secrets found across {len(blobs)} blobs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
