#!/usr/bin/env python3
"""Collect non-secret environment and test evidence metadata."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.integrations.ai.settings import AISettings


def main() -> int:
    root = ROOT
    output = root / "docs/revision/reports/summary"
    output.mkdir(parents=True, exist_ok=True)
    packages = ["fastapi", "sqlalchemy", "alembic", "pydantic", "pydantic-settings", "httpx", "uvicorn", "pytest", "pytest-cov", "ruff"]
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    ai = AISettings()
    try:
        revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=2).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True, check=True, timeout=2).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    evidence = {
        "collected_at_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor() or None,
        "cpu_count": __import__("os").cpu_count(),
        "dependency_versions": versions,
        "ai_runtime_configuration": {
            "provider": ai.ai_provider,
            "model": ai.ai_model,
            "timeout_seconds": ai.ai_timeout_seconds,
            "api_key_configured": bool(ai.gemini_api_key),
        },
        "git_commit": revision,
        "git_worktree_dirty": dirty,
        "database_for_pytest": "SQLite in-memory, enforced by tests/conftest.py; no migration executed",
        "external_ai": "not called by automated test suite; tests use mocks",
        "production_server": "not inspected from this local environment",
    }
    (output / "environment.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Wrote {output / 'environment.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
