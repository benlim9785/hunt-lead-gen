#!/usr/bin/env python3
"""Prereq checks for leads-hunt-setup wizard.

Verifies:
  1. OpenClaw is installed and an `openclaw onboard` produced a feishu binding.
  2. Sibling skills (leads-hunt, leads-hunt-outreach, leads-hunt-add-target,
     leads-hunt-voice) are installed in the active OpenClaw skills registry.
  3. <workspace>/leads-hunt/ is creatable and not already populated with a
     non-empty kb.md (use --force to override).

Exits 0 if all checks pass, 1 otherwise. Prints one ✅/❌ line per check.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_SKILLS = (
    "leads-hunt",
    "leads-hunt-outreach",
    "leads-hunt-add-target",
    "leads-hunt-voice",
)


def _run(cmd: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timed out"


def check_openclaw_binding() -> bool:
    if shutil.which("openclaw") is None:
        print("❌ OpenClaw: `openclaw` not found in PATH; install OpenClaw first.")
        return False
    rc, out, err = _run(["openclaw", "agents", "bindings"])
    if rc != 0:
        print(f"❌ OpenClaw onboard: `openclaw agents bindings` exited {rc} ({err.strip() or out.strip()})")
        return False
    haystack = (out + "\n" + err).lower()
    if "feishu" not in haystack:
        print("❌ OpenClaw onboard: no `feishu` binding found. Run `openclaw onboard` first.")
        return False
    # Best-effort: surface the binding ID if obvious (e.g. oc_xxx token).
    hint = ""
    for tok in (out + " " + err).split():
        if tok.startswith("oc_"):
            hint = f" ({tok.rstrip(',;')})"
            break
    print(f"✅ OpenClaw onboard: feishu binding found{hint}")
    return True


def check_sibling_skills() -> bool:
    rc, out, err = _run(["openclaw", "skills", "list"])
    if rc != 0:
        print(f"❌ Sibling skills: `openclaw skills list` exited {rc} ({err.strip() or out.strip()})")
        return False
    blob = (out + "\n" + err).lower()
    missing = [s for s in REQUIRED_SKILLS if s.lower() not in blob]
    if missing:
        print(f"❌ Sibling skills: missing {', '.join(missing)}")
        for s in missing:
            print(f"   → openclaw skills install ./{s}")
        return False
    print(f"✅ Sibling skills: {', '.join(REQUIRED_SKILLS)} all installed")
    return True


def check_workspace(force: bool) -> bool:
    workspace = Path(os.environ.get("OPENCLAW_WORKSPACE") or Path.home() / ".openclaw" / "workspace")
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
        check_openclaw_binding(),
        check_sibling_skills(),
        check_workspace(args.force),
    ]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
