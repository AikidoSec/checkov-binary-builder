#!/usr/bin/env python3
"""
Generate requirements.txt from Pipfile.lock for Windows ARM64 CI only.

We do not use "pipenv requirements" or "pipenv lock -r" because they can fail
depending on pipenv version (e.g. "No such option: -r" on some runners).
This script reads Pipfile.lock (JSON) and writes requirements.txt with exact pins.
Numpy is forced to >=2.1 because 2.0.2 has no Windows ARM64 wheel.

Run from checkov-src (where Pipfile.lock lives). Writes requirements.txt there.

Usage (from checkov-src):
  python ../scripts/export_requirements_win_arm64.py
  pipenv install -r requirements.txt --python 3.12 --skip-lock
"""

import json
import sys
from pathlib import Path

LOCKFILE = Path("Pipfile.lock")
REQUIREMENTS = Path("requirements.txt")
NUMPY_OVERRIDE = "numpy>=2.1"  # 2.0.2 has no win_arm64 wheel


def main() -> None:
    if not LOCKFILE.exists():
        print(f"Error: {LOCKFILE} not found. Run from checkov-src.", file=sys.stderr)
        sys.exit(1)

    data = json.loads(LOCKFILE.read_text())
    default = data.get("default", {})
    if not default:
        print("Error: no 'default' section in Pipfile.lock.", file=sys.stderr)
        sys.exit(1)

    lines = []
    for name, info in sorted(default.items()):
        if not isinstance(info, dict) or "version" not in info:
            continue
        version = info["version"].strip()
        if name.lower() == "numpy" and version == "==2.0.2":
            lines.append(NUMPY_OVERRIDE)
        else:
            lines.append(f"{name}{version}")

    REQUIREMENTS.write_text("\n".join(lines) + "\n")
    print(f"Wrote {REQUIREMENTS} ({len(lines)} packages, numpy overridden to >=2.1)")


if __name__ == "__main__":
    main()
