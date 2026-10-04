"""Load repo-root .env into os.environ (no extra dependency)."""

from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv(path: Path | None = None) -> Path | None:
    """Parse KEY=VALUE lines into os.environ. Does not override existing vars."""
    env_file = path or ENV_PATH
    if not env_file.exists():
        return None
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key or not value:
            continue
        if key not in os.environ:
            os.environ[key] = value
    return env_file
