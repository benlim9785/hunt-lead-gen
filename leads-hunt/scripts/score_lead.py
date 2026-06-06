#!/usr/bin/env python3
"""
Apply scoring rubric adjustments to a candidate.

Usage:
  echo '{"candidate":{...}}' | score_lead.py

Or as library:
  from score_lead import apply_rubric
  scored = apply_rubric(candidate, cfg)

The agent does the qualitative judgment (does this fit ICP?). This script
just normalizes adjustments based on tagged inputs.

Input candidate keys (agent-supplied):
  base_score: int 1-10  (agent's gut score before adjustments)
  has_competitor_mention: bool   (auto-skip; e.g. site mentions a competing product)
  on_top_ai_list: bool
  big_social_ai_brand: bool
  has_named_contact: bool
  size_band: "1-50"|"51-200"|"201-500"|">500"
  funded_under_5m: bool
  bootstrapped_revenue: bool
  saturated_vertical: bool   (set true if matches Saturated verticals in kb.md)
  high_yield_vertical: bool  (set true if matches High-yield verticals in kb.md)

Output:
  final_score: int
  reasons: list[str]
  ship: bool

Notes:
  Competitor keywords are pulled from cfg["negative_blacklist_keywords"] (list of
  strings). The agent is expected to do the actual page-text scan and set
  `has_competitor_mention=True` when any keyword hits.
"""
from __future__ import annotations

import json
import os
import sys


def apply_rubric(c: dict, cfg: dict) -> dict:
    base = int(c.get("base_score", 5))
    reasons = []
    score = base

    # Auto-skip on competitor mention. Backward-compat alias kept for
    # candidates that still set has_byteplus_mention.
    if c.get("has_competitor_mention") or c.get("has_byteplus_mention"):
        return {
            "final_score": 0,
            "reasons": ["AUTO-SKIP: competitor product mention detected on candidate's site"],
            "ship": False,
        }
    if c.get("on_top_ai_list"):
        score -= 3
        reasons.append("on top-AI-tools list -3")
    if c.get("big_social_ai_brand"):
        score -= 3
        reasons.append(">50K + AI-brand -3")
    if c.get("has_named_contact"):
        score += 1
        reasons.append("named contact +1")
    size = c.get("size_band", "")
    if size == "1-50":
        score += 1
        reasons.append("size 1-50 (target ICP) +1")
    if c.get("funded_under_5m"):
        score += 1
        reasons.append("funded ≤$5M +1")
    if c.get("bootstrapped_revenue"):
        score += 1
        reasons.append("bootstrapped+revenue +1")
    if c.get("saturated_vertical"):
        score -= 2
        reasons.append("saturated vertical -2")
    if c.get("high_yield_vertical"):
        score += 1
        reasons.append("high-yield vertical +1")

    final = max(0, min(10, score))
    return {
        "final_score": final,
        "reasons": reasons,
        "ship": final >= cfg.get("score_floor", 8),
    }


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    SCRIPT_DIR = Path(__file__).resolve().parent
    sys.path.insert(0, str(SCRIPT_DIR))
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    from _config import load_config
    cfg = load_config()
    raw = sys.stdin.read()
    if not raw.strip():
        print("usage: echo '<candidate-json>' | score_lead.py", file=sys.stderr)
        sys.exit(2)
    candidate = json.loads(raw)
    if "candidate" in candidate:
        candidate = candidate["candidate"]
    print(json.dumps(apply_rubric(candidate, cfg), indent=2))
