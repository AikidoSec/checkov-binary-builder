#!/usr/bin/env python3
"""
Patch checkov's __init__.py files so dynamic __all__ (glob-based) works when
running as a Nuitka-compiled binary (no .py files on disk).

Run from repo root after checkout, before Nuitka build. If
nuitka-generated/nuitka-include-modules.txt exists it is used; otherwise
modules are discovered by scanning the checkov package on disk (CI-friendly).

For numpy.random.randbits, the Nuitka build uses scripts/entry_nuitka.py as
the entry point; it imports 'random' before running checkov.main.

No fork required.
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

# --- Module discovery ---


def load_module_list(path: Path) -> List[str]:
    """Load full module names from file. Returns [] if file missing."""
    if not path.exists():
        return []
    
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def path_to_module(path: Path, checkov_root: Path) -> str:
    """Turn a .py path under checkov_root into a checkov.* module name."""
    rel = path.relative_to(checkov_root)
    parts = rel.parts
    
    if path.name == "__init__.py":
        return "checkov." + ".".join(parts[:-1]) if parts[:-1] else "checkov"
    
    name = "checkov." + ".".join(parts[:-1] + (path.stem,)) if parts[:-1] else "checkov." + path.stem
    return name


def discover_modules(checkov_root: Path) -> List[str]:
    """Discover all checkov.* module names by scanning the package directory."""
    modules = []
    for path in checkov_root.rglob("*.py"):
        try:
            modules.append(path_to_module(path, checkov_root))
        except ValueError:
            continue
        
    return sorted(set(modules))


def init_path_to_package(init_path: Path, checkov_root: Path) -> Optional[str]:
    """e.g. checkov/terraform/checks/__init__.py -> checkov.terraform.checks."""
    try:
        rel = init_path.parent.relative_to(checkov_root)
    except ValueError:
        return None
    return "checkov." + ".".join(rel.parts) if rel.parts else "checkov"


def direct_children(prefix: str, modules: List[str]) -> List[str]:
    """Immediate submodule names (e.g. checkov.terraform.checks -> [resource, graph_checks])."""
    prefix_dot = prefix + "."
    depth = len(prefix.split("."))
    children = set()
    
    for name in modules:
        if not name.startswith(prefix_dot) or name == prefix:
            continue
        
        parts = name.split(".")
        if len(parts) > depth:
            children.add(parts[depth])
            
    return sorted(children)


# --- Glob __all__ detection and patching ---


def uses_glob_all(content: str) -> bool:
    """True if file builds __all__ via glob/pathlib (breaks in Nuitka standalone)."""
    if "__all__" not in content:
        return False
    
    return (
        "glob.glob" in content
        or "Path(__file__).parent.glob" in content
        or ("Path(__file__).parent" in content and ".glob(" in content)
    )


def _is_block_start(line: str) -> bool:
    return (
        "from os.path import" in line
        or line.strip() == "import glob"
        or "from pathlib import" in line
    )


def _is_all_line_with_glob(line: str) -> bool:
    return "__all__" in line and "=" in line and "[" in line and (
        "glob" in line or "Path(__file__)" in line or "basename" in line or ".stem" in line
    )


def replace_glob_all_with_static(content: str, static_all: List[str]) -> Tuple[str, bool]:
    """
    Replace the glob/pathlib __all__ block with a static list.
    Returns (new_content, True) if replaced, (content, False) otherwise.
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return content, False

    static_line = f"__all__ = {static_all!r}\n"
    block_start = None

    for i, line in enumerate(lines):
        if block_start is None and _is_block_start(line):
            block_start = i
            continue

        if block_start is not None and "modules =" in line and "glob" in line:
            continue

        if "__all__" in line and "=" in line and "[" in line:
            if block_start is not None:
                new_lines = lines[:block_start] + [static_line] + lines[i + 1:]
                return "".join(new_lines), True
            
            if _is_all_line_with_glob(line):
                new_lines = lines[:i] + [static_line] + lines[i + 1:]
                return "".join(new_lines), True
            
            block_start = None
        elif block_start is not None and line.strip() and not line.strip().startswith("#"):
            if "import " not in line and "from " not in line and "modules =" not in line:
                block_start = None

    return content, False


def _path_under_root(path: Path, root: Path) -> Optional[Path]:
    """Return resolved path if it is under root; else None. Used to constrain file writes."""
    try:
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
        return resolved
    except ValueError:
        return None


def patch_one_init(init_path: Path, package: str, modules: List[str], checkov_root: Path) -> bool:
    """Patch one __init__.py if it uses glob-based __all__. Returns True if patched."""
    safe_path = _path_under_root(init_path, checkov_root)
    if safe_path is None:
        return False
    
    content = safe_path.read_text(encoding="utf-8")
    if not uses_glob_all(content):
        return False
    
    children = direct_children(package, modules)
    if not children:
        return False
    
    new_content, replaced = replace_glob_all_with_static(content, children)
    if not replaced:
        return False
    
    safe_path.write_text(new_content, encoding="utf-8")
    return True


# --- Main ---


def find_checkov_root(root: Path) -> Optional[Path]:
    """Resolve checkov package dir (checkov-src/checkov or checkov/)."""
    for candidate in (root / "checkov-src" / "checkov", root / "checkov"):
        if candidate.is_dir():
            return candidate
        
    return None


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    checkov_root = find_checkov_root(root)
    
    if not checkov_root:
        print("Error: checkov not found at checkov-src/checkov or checkov/ (run after checkout).", file=sys.stderr)
        sys.exit(1)

    module_list_path = root / "nuitka-generated" / "nuitka-include-modules.txt"
    modules = load_module_list(module_list_path)
    
    if not modules:
        print(f"Module list not found ({module_list_path}); discovering from checkov package.", file=sys.stderr)
        modules = discover_modules(checkov_root)
        
        if not modules:
            print("No checkov modules found; skipping __all__ patches.", file=sys.stderr)
            return
        
        print(f"Discovered {len(modules)} module(s).")

    patched = []
    for init_path in checkov_root.rglob("__init__.py"):
        package = init_path_to_package(init_path, checkov_root)
        
        if not package:
            continue
        
        if patch_one_init(init_path, package, modules, checkov_root):
            rel = init_path.relative_to(root)
            patched.append(str(rel))
            n = len(direct_children(package, modules))
            print(f"Patched: {rel} -> __all__ = {n} direct children")

    if not patched:
        print("No __init__.py files with glob-based __all__ needed patching.", file=sys.stderr)
    else:
        print(f"Patched {len(patched)} file(s) for Nuitka runtime.")


if __name__ == "__main__":
    main()
