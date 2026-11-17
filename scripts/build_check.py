#!/usr/bin/env python
"""Fail the build if confidential raw data or oversized files are deployable.

Checks
------
* No raw-pack filename (ball_by_ball.csv, matches.csv, ...) anywhere in the repo
  outside ``data_raw/``.
* No ``data_raw`` path segment in the deploy roots.
* No file larger than 5 MB in the deploy roots (``frontend/dist``,
  ``data_derived``, ``backend``).
* ``/data_raw/`` is present in ``.gitignore``.

Run from the project root:
    python scripts/build_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOY_ROOTS = ("frontend/dist", "data_derived", "backend")
FORBIDDEN_NAMES = {
    "ball_by_ball.csv",
    "matches.csv",
    "competitions.csv",
    "competition_team_player_mapping.csv",
    "playing_eleven.csv",
    "teams.csv",
}
MAX_BYTES = 5 * 1024 * 1024
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "data_raw"}


def iter_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file():
            yield path


def check(repo: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    checked = 0

    for path in iter_files(repo):
        parts = set(path.relative_to(repo).parts)
        if parts & SKIP_DIRS:
            continue
        checked += 1
        if path.name in FORBIDDEN_NAMES:
            errors.append(f"Raw-pack filename outside data_raw: {path.relative_to(repo)}")

    for root_name in DEPLOY_ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        for path in iter_files(root):
            rel = path.relative_to(repo)
            if "data_raw" in rel.parts:
                errors.append(f"data_raw path in deploy bundle: {rel}")
            size = path.stat().st_size
            if size > MAX_BYTES:
                errors.append(
                    f"Deploy file larger than 5 MB: {rel} ({size / (1024 * 1024):.2f} MB)"
                )

    gitignore = repo / ".gitignore"
    if not gitignore.exists() or "/data_raw/" not in gitignore.read_text(encoding="utf-8"):
        errors.append(".gitignore must contain '/data_raw/'")

    return errors, checked


def main(repo: Path | None = None) -> int:
    repo = (repo or Path(__file__).resolve().parents[1]).resolve()
    errors, checked = check(repo)

    if errors:
        print("BUILD CHECK FAILED")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Build check passed ({checked} files scanned; raw pack isolated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
