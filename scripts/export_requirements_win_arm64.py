#!/usr/bin/env python3
"""
Generate requirements.txt from Pipfile.lock for Windows ARM64 CI only.

We do not use "pipenv requirements" or "pipenv lock -r" because they can fail
depending on pipenv version (e.g. "No such option: -r" on some runners).
This script reads Pipfile.lock (JSON) and writes requirements.txt with exact pins.
- Numpy is forced to >=2.1 because 2.0.2 has no Windows ARM64 wheel.
- Optional: pass a path to a file listing package names to skip (one per line).
  The CI retry loop appends packages that have no win_arm64 wheel so we don't
  maintain a hardcoded list.

Run from checkov-src (where Pipfile.lock lives). Writes requirements.txt there.

Usage (from checkov-src):
  python ../scripts/export_requirements_win_arm64.py [skip_packages.txt]
  pipenv install -r requirements.txt --python 3.12 --skip-lock
"""

import json
import sys
from pathlib import Path

LOCKFILE = Path("Pipfile.lock")
REQUIREMENTS = Path("requirements.txt")
NUMPY_OVERRIDE = "numpy>=2.1"  # 2.0.2 has no win_arm64 wheel


def load_skip_packages(path: Path) -> set[str]:
    """Load package names to skip (one per line). Missing/empty file = empty set."""
    if not path.exists():
        return set()
    return {line.strip().lower() for line in path.read_text().splitlines() if line.strip()}


def main() -> None:
    skip_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    skip_packages = load_skip_packages(skip_file) if skip_file else set()

    if not LOCKFILE.exists():
        print(f"Error: {LOCKFILE} not found. Run from checkov-src.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(LOCKFILE.read_text())
    default = data.get("default", {})
    if not default:
        print("Error: no 'default' section in Pipfile.lock.", file=sys.stderr)
        sys.exit(1)

    lines = []
    skipped = []
    for name, info in sorted(default.items()):
        if not isinstance(info, dict) or "version" not in info:
            continue
        if name.lower() in skip_packages:
            skipped.append(name)
            continue
        version = info["version"].strip()
        if name.lower() == "numpy" and version == "==2.0.2":
            lines.append(NUMPY_OVERRIDE)
        else:
            lines.append(f"{name}{version}")

    REQUIREMENTS.write_text("\n".join(lines) + "\n")
    msg = f"Wrote {REQUIREMENTS} ({len(lines)} packages, numpy overridden to >=2.1"
    if skipped:
        msg += f", skipped: {', '.join(sorted(skipped))}"
    print(msg)


if __name__ == "__main__":
    main()
