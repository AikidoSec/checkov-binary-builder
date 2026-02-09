#!/usr/bin/env python3
"""
Patch checkov's __init__.py files so dynamic __all__ (glob-based) works when
running as a Nuitka-compiled binary (no .py files on disk).

Run from repo root after discover_checkov_modules.py. Patches the checkov
source in place so Nuitka compiles the patched code and runtime discovery works.

No fork required: run this in CI after checkout, before Nuitka build.
"""

from __future__ import print_function

import sys
from pathlib import Path


def load_module_list(path):
    """Load full module names from discovery output."""
    p = Path(path)
    if not p.exists():
        print("Error: module list not found: {}".format(p), file=sys.stderr)
        sys.exit(1)
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def package_from_init_path(init_path, checkov_root):
    """Convert path like checkov/terraform/checks/__init__.py to checkov.terraform.checks."""
    try:
        rel = init_path.parent.relative_to(checkov_root)
    except ValueError:
        return None
    # checkov_root is the package dir (e.g. .../checkov), so package name is checkov.terraform.checks
    parts = rel.parts
    if not parts:
        return "checkov"
    return "checkov." + ".".join(parts)


def direct_children(prefix, modules):
    """Immediate submodule names for a package (e.g. checkov.terraform.checks -> [resource, graph_checks])."""
    prefix_dot = prefix + "."
    n = len(prefix.split("."))
    children = set()
    for m in modules:
        if not m.startswith(prefix_dot) or m == prefix:
            continue
        parts = m.split(".")
        if len(parts) > n:
            children.add(parts[n])
    return sorted(children)


def has_glob_all_pattern(content):
    """True if file uses glob/pathlib to build __all__ (will break in Nuitka standalone)."""
    if "glob.glob" in content and "__all__" in content:
        return True
    if "Path(__file__).parent.glob" in content and "__all__" in content:
        return True
    if "Path(__file__).parent" in content and ".glob(" in content and "__all__" in content:
        return True
    return False


def find_and_replace_glob_all_block(content, static_all_list):
    """
    Find the block that builds __all__ via glob/pathlib and replace with static list.
    Returns (new_content, True) if replaced, (content, False) otherwise.
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return content, False
    i = 0
    block_start = None
    while i < len(lines):
        line = lines[i]
        # Start of block: os.path / glob / pathlib
        if block_start is None and (
            "from os.path import" in line
            or (line.strip() == "import glob")
            or "from pathlib import" in line
        ):
            block_start = i
            i += 1
            continue
        # Continuation: modules = glob.glob or similar
        if block_start is not None and "modules =" in line and "glob" in line:
            i += 1
            continue
        # End of block: __all__ = [...]
        if "__all__" in line and "=" in line and "[" in line:
            if block_start is not None:
                static_line = "__all__ = {}\n".format(repr(static_all_list))
                new_lines = lines[:block_start] + [static_line] + lines[i + 1 :]
                return "".join(new_lines), True
            # __all__ line without a prior block start (e.g. pathlib one-liner)
            if "glob" in line or "Path(__file__)" in line or "basename" in line or ".stem" in line:
                static_line = "__all__ = {}\n".format(repr(static_all_list))
                new_lines = lines[:i] + [static_line] + lines[i + 1 :]
                return "".join(new_lines), True
            block_start = None
        elif block_start is not None and line.strip() and not line.strip().startswith("#"):
            # Non-empty line that doesn't look like block continuation
            if "import " not in line and "from " not in line and "modules =" not in line:
                block_start = None
        i += 1
    return content, False


def patch_init_file(init_path, package, modules, checkov_root):
    """Patch one __init__.py if it uses glob-based __all__."""
    content = init_path.read_text(encoding="utf-8")
    if not has_glob_all_pattern(content):
        return False
    children = direct_children(package, modules)
    if not children:
        return False
    new_content, replaced = find_and_replace_glob_all_block(content, children)
    if not replaced:
        return False
    init_path.write_text(new_content, encoding="utf-8")
    return True


def main():
    root = Path(__file__).resolve().parent.parent
    # Support checkout at checkov/ or checkov-src/ (CI uses path: checkov-src)
    checkov_root = root / "checkov-src" / "checkov"
    if not checkov_root.is_dir():
        checkov_root = root / "checkov"
    if not checkov_root.is_dir():
        print("Error: checkov not found at checkov-src/checkov or checkov/ (run after checkout).", file=sys.stderr)
        sys.exit(1)

    module_list_path = root / "nuitka-generated" / "nuitka-include-modules.txt"
    modules = load_module_list(module_list_path)

    patched = []
    for init_path in checkov_root.rglob("__init__.py"):
        package = package_from_init_path(init_path, checkov_root)
        if not package:
            continue
        if patch_init_file(init_path, package, modules, checkov_root):
            rel = init_path.relative_to(root)
            patched.append(str(rel))
            print("Patched: {} -> __all__ = {} direct children".format(rel, len(direct_children(package, modules))))

    if not patched:
        print("No __init__.py files with glob-based __all__ needed patching.", file=sys.stderr)
    else:
        print("Patched {} file(s) for Nuitka runtime.".format(len(patched)))


if __name__ == "__main__":
    main()
