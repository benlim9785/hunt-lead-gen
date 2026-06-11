#!/usr/bin/env python3
"""Initialize <workspace>/leads-hunt/ state directory.

Creates:
  <workspace>/leads-hunt/data/
  <workspace>/leads-hunt/browser-profile/
  <workspace>/leads-hunt/kb.md  (legacy compatibility skeleton only)

`kb.md` is kept for backward compatibility and optional AE notes, but it is no
longer the runtime source of truth. Runtime lead data lives in the configured
Lark Base and per-AE metadata lives in `<workspace>/leads-hunt/config.json`.

Idempotent: re-running on an existing dir is a no-op unless --force is given,
in which case the compatibility `kb.md` is rewritten to the empty skeleton
(existing content lost).

Workspace path resolves from $AIME_WORKSPACE_PATH when available.
Override with --workspace <path>.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

KB_SKELETON = """\
# leads-hunt compatibility notes

Legacy local notes file kept for backward compatibility only.

Runtime source of truth:
- Leads -> Lark Base `Leads`
- Customers -> Lark Base `Customers`
- Skip List -> Lark Base `Skip List`
- Discovery Patterns -> Lark Base `Discovery Patterns`

Use this file only for optional AE notes that do not need to participate in the
runtime pipeline.

## Customers

_(Legacy compatibility section — canonical runtime data lives in Lark Base.)_

## Shipped Leads

_(Legacy compatibility section — Phase D now upserts shipped leads to Base.)_

## Skip List

_(Legacy compatibility section — Layer 1 now reads the Base `Skip List` table.)_

## Discovery Patterns Learned

_(Legacy compatibility section — Phase B now reads recent patterns from Base.)_
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
    ap.add_argument("--force", action="store_true", help="Rewrite legacy kb.md skeleton even if non-empty")
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
        print(f"populated empty {kb} with compatibility skeleton")
    elif args.force:
        kb.write_text(KB_SKELETON, encoding="utf-8")
        print(f"⚠  rewrote {kb} (--force; previous content lost)")
    else:
        print(f"kept existing {kb} (use --force to overwrite the compatibility skeleton)")

    print(f"state dir ready: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
