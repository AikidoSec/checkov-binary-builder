#!/usr/bin/env python3
"""
Nuitka entry point for Checkov.

Ensures stdlib 'random' is imported before any other code runs, so
numpy.random.bit_generator (C extension) can resolve random.randbits
when loaded in the Nuitka-compiled binary.

Uses direct import + Checkov().run() instead of runpy.run_module() because
Nuitka's module loader does not implement get_code(), which runpy requires.
"""
import random  # noqa: F401 - must run first for numpy C extension
import sys

if __name__ == "__main__":
    import checkov.main as checkov_main

    exit_code = checkov_main.Checkov().run()
    sys.exit(exit_code if exit_code is not None else 0)
