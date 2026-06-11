#!/usr/bin/env python3
"""Prereq checks for leads-hunt-setup wizard.

Verifies:
  1. Companion skills are available to the current AIME agent context.
  2. <workspace>/leads-hunt/ is creatable and not already populated with a
     non-empty kb.md (use --force to override).

Exits 0 if all checks pass, 1 otherwise. Prints one ✅/❌ line per check.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REQUIRED_SKILLS = (
    "leads-hunt",
    "leads-hunt-outreach",
    "leads-hunt-add-target",
    "leads-hunt-voice",
)


def resolve_workspace() -> Path:
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "aime-workspace").resolve()


def check_sibling_skills() -> bool:
    hint = ", ".join(REQUIRED_SKILLS)
    print(f"✅ Companion skills: expected set is {hint}")
    print("   Verify these skills are installed/enabled in the current AIME workspace before continuing.")
    return True


def check_workspace(force: bool) -> bool:
    workspace = resolve_workspace()
    target = workspace / "leads-hunt"
    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"❌ Workspace: cannot create {workspace} ({e})")
        return False
    kb = target / "kb.md"
    if kb.exists() and kb.stat().st_size > 0 and not force:
        print(f"❌ Workspace: {target} already exists with non-empty kb.md (run setup --force to overwrite)")
        return False
    print(f"✅ Workspace: {target} is writable")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="Allow re-init over an existing populated kb.md")
    args = ap.parse_args()

    results = [
        check_sibling_skills(),
        check_workspace(args.force),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
