#!/usr/bin/env python3
"""Validate that the Database Schema Documentation migration table
matches the actual number of Alembic migration files on disk.

Usage:
    python scripts/check_migration_docs.py

Exit codes:
    0  — migration count in docs matches the filesystem
    1  — mismatch detected (docs are stale)
"""

import pathlib
import re
import sys

# Paths are relative to the project root
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "alembic" / "versions"
DOCS_FILE = PROJECT_ROOT / "documentation" / "Database_Schema_Documentation.md"

# Pattern that matches "Total migrations: N" in the docs
TOTAL_RE = re.compile(r"\*\*Total migrations:\s*(\d+)\*\*", re.IGNORECASE)


def count_migration_files() -> int:
    """Count .py migration files (excluding __pycache__)."""
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: migrations directory not found: {MIGRATIONS_DIR}")
        sys.exit(1)
    return sum(
        1
        for f in MIGRATIONS_DIR.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    )


def read_docs_count() -> int | None:
    """Extract the 'Total migrations: N' value from the docs file."""
    if not DOCS_FILE.is_file():
        print(f"ERROR: docs file not found: {DOCS_FILE}")
        sys.exit(1)
    text = DOCS_FILE.read_text(encoding="utf-8")
    match = TOTAL_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def main() -> None:
    fs_count = count_migration_files()
    docs_count = read_docs_count()

    if docs_count is None:
        print(
            f"ERROR: Could not find '**Total migrations: N**' in {DOCS_FILE.name}.\n"
            f"       Please add that line to the Alembic Migrations section."
        )
        sys.exit(1)

    if fs_count != docs_count:
        print(
            f"ERROR: {MIGRATIONS_DIR.relative_to(PROJECT_ROOT)} has {fs_count} "
            f"migration file(s) but docs say {docs_count}.\n"
            f"       Please update {DOCS_FILE.relative_to(PROJECT_ROOT)} migration table."
        )
        sys.exit(1)

    print(
        f"OK: migration count consistent — {fs_count} file(s) in "
        f"{MIGRATIONS_DIR.relative_to(PROJECT_ROOT)}, docs say {docs_count}."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
