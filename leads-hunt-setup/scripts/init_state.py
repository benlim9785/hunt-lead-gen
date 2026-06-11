#!/usr/bin/env python3
"""Initialize <workspace>/leads-hunt/ state directory.

Creates:
  <workspace>/leads-hunt/data/
  <workspace>/leads-hunt/browser-profile/
  <workspace>/leads-hunt/kb.md  (with empty H2 skeleton)

Idempotent: re-running on an existing dir is a no-op unless --force is given,
in which case kb.md is rewritten to the empty skeleton (existing content lost).

Workspace path resolves from $AIME_WORKSPACE_PATH when available.
Override with --workspace <path>.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

KB_SKELETON = """\
# leads-hunt knowledge base

This file is the AE's source of truth. Every shipped lead, every tracked
customer, every pattern learned, every hard-skip — all lives here. Read by
Layer 2 dedup and by Phase B's discovery-pattern feedback loop.

## Customers

_(BytePlus customers you're tracking. One H3 per customer.)_

## Shipped Leads

_(Leads delivered to Lark digests. Phase D appends here automatically.)_

## Skip List

_(Hard-skip companies — name on its own line. Layer 1 reads this.)_

## Discovery Patterns Learned

_(Saturated verticals, high-yield segments, hypotheses to retire. Phase B
reads recent entries from here.)_
"""


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / "aime-workspace").resolve()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    ap.add_argument("--force", action="store_true", help="Rewrite kb.md skeleton even if non-empty")
    args = ap.parse_args()

    root = resolve_workspace(args.workspace) / "leads-hunt"
    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "browser-profile").mkdir(exist_ok=True)

    kb = root / "kb.md"
    if not kb.exists():
        kb.write_text(KB_SKELETON, encoding="utf-8")
        print(f"created {kb}")
    elif kb.stat().st_size == 0:
        kb.write_text(KB_SKELETON, encoding="utf-8")
        print(f"populated empty {kb} with skeleton")
    elif args.force:
        kb.write_text(KB_SKELETON, encoding="utf-8")
        print(f"⚠  rewrote {kb} (--force; previous content lost)")
    else:
        print(f"kept existing {kb} (use --force to overwrite)")

    print(f"state dir ready: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
