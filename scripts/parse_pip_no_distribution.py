#!/usr/bin/env python3
"""
Read pip stderr (stdin) and print the package name from a line like:
  ERROR: No matching distribution found for some-package==1.2.3
Used by Windows ARM64 CI to discover which package to skip and retry.
Prints nothing if no such line is found.
"""
import re
import sys

for line in sys.stdin:
    m = re.search(r"No matching distribution found for ([^=]+)==", line)
    if m:
        print(m.group(1))
        break
