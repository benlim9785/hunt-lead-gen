#!/usr/bin/env python3
"""
Main entrypoint for leads-hunt skill.

Phases:
  sso-check    Phase A: smoke-test Sales Nav session, halt day if expired.
  discover     Phase B: print discovery brief for ONE topic. Agent does research.
  discover-all Phase B fan-out: run discover for every enabled topic in registry,
               with internal staggering to avoid Sales Nav fingerprint pile-up.
  dedup        Phase C: walk 3-layer dedup for ONE topic, write per-topic leads CSV.
  dedup-all    Phase C fan-out: run dedup for every enabled topic, staggered.
  deliver      Phase D: aggregate, write Lark digest to stdout.

The `*-all` variants are what cron uses. Per-topic invocations are kept for
manual runs and debugging.

Topics are NOT hardcoded — they come from the registry (references/topics/*.md).
Add a new topic = drop a markdown file with frontmatter, no code edit needed.
See `topic_registry.py` for schema.

Usage:
  run_topic.py --phase sso-check
  run_topic.py --phase discover-all
  run_topic.py --phase dedup-all
  run_topic.py --phase deliver

  # Manual / debugging:
  run_topic.py --phase discover --topic aigc-visual
  run_topic.py --phase dedup --topic aigc-visual

Exit codes:
  0  success
  1  failed (logged details to run-log)
  2  bad invocation
  3  Sales Nav session expired (Phase A; or Phase C halted mid-run)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


# Stagger between topics inside fan-out phases, in seconds.
# Discovery: short stagger — both launch headless browsers, avoid simultaneous.
# Dedup: longer stagger — each topic fires N×Sales-Nav XHRs, bunching looks bot-like.
DISCOVER_STAGGER_S = 300   # 5 min
DEDUP_STAGGER_S = 900      # 15 min


def _validate_topic(slug: str, cfg) -> int:
    """Return 0 if topic exists and is enabled, else 2 with a helpful error."""
    from topic_registry import load_topics, get_topic
    t = get_topic(slug, cfg)
    if t is None:
        valid = [x["slug"] for x in load_topics(cfg, include_disabled=True)]
        print(f"Unknown or disabled topic: {slug!r}", file=sys.stderr)
        print(f"Known topics: {', '.join(valid) or '(none)'}", file=sys.stderr)
        return 2
    return 0


def cmd_sso_check(args, cfg) -> int:
    from sales_nav_check import smoke_test
    return smoke_test(cfg)


def cmd_discover(args, cfg) -> int:
    if not args.topic:
        print("--topic required for discover phase", file=sys.stderr)
        return 2
    rc = _validate_topic(args.topic, cfg)
    if rc:
        return rc
    from discover import print_brief
    from topic_registry import cfg_for_topic
    return print_brief(args.topic, cfg_for_topic(cfg, args.topic), dry_run=args.dry_run)


def cmd_dedup(args, cfg) -> int:
    if not args.topic:
        print("--topic required for dedup phase", file=sys.stderr)
        return 2
    rc = _validate_topic(args.topic, cfg)
    if rc:
        return rc
    from dedup_pipeline import run_dedup
    from topic_registry import cfg_for_topic
    return run_dedup(args.topic, cfg_for_topic(cfg, args.topic), dry_run=args.dry_run)


def cmd_discover_all(args, cfg) -> int:
    """Fan-out: run discover for every enabled topic with stagger."""
    from discover import print_brief
    from topic_registry import load_topics, cfg_for_topic
    topics = load_topics(cfg)
    if not topics:
        print("[discover-all] no enabled topics in registry; nothing to do", file=sys.stderr)
        return 0
    print(f"[discover-all] running over {len(topics)} enabled topic(s): "
          f"{', '.join(t['slug'] for t in topics)}", file=sys.stderr)
    failures = 0
    for i, t in enumerate(topics):
        if i > 0 and not args.dry_run:
            print(f"[discover-all] stagger sleep {DISCOVER_STAGGER_S}s before {t['slug']}",
                  file=sys.stderr)
            time.sleep(DISCOVER_STAGGER_S)
        print(f"\n{'=' * 60}\n[discover-all] === topic: {t['slug']} ===\n{'=' * 60}\n",
              file=sys.stderr)
        try:
            rc = print_brief(t["slug"], cfg_for_topic(cfg, t["slug"]), dry_run=args.dry_run)
            if rc != 0:
                failures += 1
                print(f"[discover-all] {t['slug']} exited rc={rc}", file=sys.stderr)
        except Exception as e:
            failures += 1
            print(f"[discover-all] {t['slug']} crashed: {e}", file=sys.stderr)
    return 1 if failures else 0


def cmd_dedup_all(args, cfg) -> int:
    """Fan-out: run dedup for every enabled topic with stagger.

    If any topic returns rc=3 (Sales Nav session expired mid-run), abort the
    rest of the fan-out and propagate rc=3 — Phase D's sentinel check will
    keep deliver from running, and the canary alert from Phase A tomorrow
    will surface it.
    """
    from dedup_pipeline import run_dedup
    from topic_registry import load_topics, cfg_for_topic
    topics = load_topics(cfg)
    if not topics:
        print("[dedup-all] no enabled topics in registry; nothing to do", file=sys.stderr)
        return 0
    print(f"[dedup-all] running over {len(topics)} enabled topic(s): "
          f"{', '.join(t['slug'] for t in topics)}", file=sys.stderr)
    failures = 0
    for i, t in enumerate(topics):
        if i > 0 and not args.dry_run:
            print(f"[dedup-all] stagger sleep {DEDUP_STAGGER_S}s before {t['slug']}",
                  file=sys.stderr)
            time.sleep(DEDUP_STAGGER_S)
        print(f"\n{'=' * 60}\n[dedup-all] === topic: {t['slug']} ===\n{'=' * 60}\n",
              file=sys.stderr)
        try:
            rc = run_dedup(t["slug"], cfg_for_topic(cfg, t["slug"]), dry_run=args.dry_run)
            if rc == 3:
                print(f"[dedup-all] HALT: {t['slug']} returned rc=3 (Sales Nav session expired); "
                      f"aborting remaining topics", file=sys.stderr)
                return 3
            if rc != 0:
                failures += 1
                print(f"[dedup-all] {t['slug']} exited rc={rc}", file=sys.stderr)
        except Exception as e:
            failures += 1
            print(f"[dedup-all] {t['slug']} crashed: {e}", file=sys.stderr)
    return 1 if failures else 0


def cmd_deliver(args, cfg) -> int:
    from deliver_lark import deliver
    return deliver(cfg, dry_run=args.dry_run)


PHASES = {
    "sso-check": cmd_sso_check,
    "discover": cmd_discover,
    "discover-all": cmd_discover_all,
    "dedup": cmd_dedup,
    "dedup-all": cmd_dedup_all,
    "deliver": cmd_deliver,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", required=True, choices=list(PHASES.keys()))
    ap.add_argument("--topic",
                    help="Topic slug (only used by per-topic phases). "
                         "Validated against topic_registry at runtime — "
                         "no hardcoded list. See references/topics/*.md.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip API calls and external writes; print what would be done.")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    from _config import load_config
    cfg = load_config()
    return PHASES[args.phase](args, cfg)


if __name__ == "__main__":
    sys.exit(main())
