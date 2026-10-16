#!/usr/bin/env python3
# Vendored from sunnypilot/sunnypilot@master:tools/release/release_files.py
#
# The fork's `dev-c3x` branch is derived from a prebuilt branch and does not
# carry `tools/release/` (upstream strips it from published branches). This is
# the exact tool the upstream prebuilt build uses to list the tracked release
# tree; it is vendored here so the build is reproducible without pulling from
# upstream at build time.
#
# NOTE: ROOT is derived from this file's location (HERE/../..), so this copy
# must stay at <repo-root>/ci/agnos/release_files.py for the relative paths it
# prints to line up with the checkout root.
import os
import re
import subprocess
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../.."))

blacklist = [
  ".git/",
  ".venv/",
  ".github/workflows/",

  # fork-specific: CI infrastructure is not release content
  "^ci/",

  "matlab.*.md",

  # no LFS or submodules in release
  ".lfsconfig",
  ".gitattributes",
  ".git$",
  ".gitmodules",
  ".run/",
  ".idea/",
]

# gets you through the blacklist
whitelist: list[str] = []


if __name__ == "__main__":
  tracked_files = subprocess.check_output(["git", "ls-files", "-z", "--recurse-submodules"], cwd=ROOT).split(b"\0")
  for tracked_file in tracked_files:
    if not tracked_file:
      continue

    rf = os.fsdecode(tracked_file)
    if not os.getenv("INCLUDE_BIG_MODEL") and rf.startswith("openpilot/selfdrive/modeld/models/big_driving_tinygrad.pkl"):
      continue
    blacklisted = any(re.search(p, rf) for p in blacklist)
    whitelisted = any(re.search(p, rf) for p in whitelist)
    if blacklisted and not whitelisted:
      continue

    sys.stdout.buffer.write(tracked_file + b"\0")
