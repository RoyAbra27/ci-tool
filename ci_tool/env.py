"""Tiny .env loader: KEY=VALUE lines, never overrides real environment.
Misconfigured lines warn on stderr instead of loading: a missing optional
key silently skips its source, so a malformed one must not look identical
(CHALLENGES.md, the .env comment gotcha)."""

import os
import sys
from pathlib import Path


def load_env(path: str | Path = ".env") -> None:
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#"):
            key, sep, value = line.lstrip("#").strip().partition("=")
            key = key.strip()
            if sep and value.strip() and key.isidentifier():
                print(
                    f".env: {key} has a value but the line is commented out;"
                    " remove the leading '#' to use it",
                    file=sys.stderr,
                )
            continue
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"')
        if not value or value.startswith("#"):
            print(f".env: {key} is empty or comment-shaped; not loaded", file=sys.stderr)
            continue
        os.environ.setdefault(key, value)
