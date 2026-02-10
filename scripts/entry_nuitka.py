#!/usr/bin/env python3
"""
Nuitka entry point for Checkov.

Ensures stdlib 'random' is imported before any other code runs, so
numpy.random.bit_generator (C extension) can resolve random.randbits
when loaded in the Nuitka-compiled binary.
"""
import random  # noqa: F401 - must run first for numpy C extension
import runpy
import sys

if __name__ == "__main__":
    runpy.run_module("checkov.main", run_name="__main__")
    sys.exit(0)
