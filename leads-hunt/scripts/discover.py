#!/usr/bin/env python3
"""
Phase B: print a discovery brief for the topic.

This script does NOT do the actual web research (that's the agent's job).
It prepares a "brief" the agent reads at start of Phase B:

  - today's day-type and method
  - last 5 entries from feedback-{topic}.md (per-topic agent reflections)
  - recent kb.md patterns (good/bad signals from prior shipments)  [Phase 2]
  - the topic's ICP file
  - target candidate count (~18)

After printing the brief, the agent does browser research, scoring, and
writes the candidates JSON to:
  {LEADS_HUNT_HOME}/data/lead-gen/candidates/{topic}-YYYY-MM-DD.json

Format the agent should produce:
[
  {
    "company": "Acme AI",
    "domain": "acme.ai",
    "topic": "aigc-visual",
    "score": 8,
    "industry": "Marketing & Advertising",
    "region": "US",
    "employee_count": 12,
    "outreach_angle": "...",
    "discovered_via": "YC F2025 batch sweep",
    "rationale": "..."
  },
  ...
]
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent


def _kb():
    """Lazy import of kb module (built in Phase 2)."""
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        import kb  # type: ignore
        return kb
    except ImportError:
        return None


def _today_myt() -> datetime.date:
    """Return today's date in Asia/Kuala_Lumpur (UTC+8, no DST)."""
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date()


def _day_type(today: datetime.date, cfg) -> tuple[str, str]:
    """Return (day_type_letter, day_type_label)."""
    weekday = str(today.weekday())  # Mon=0
    letter = cfg["day_type_map"].get(weekday, "B")
    label = cfg["day_type_methods"].get(letter, "")
    return letter, label


def _read_feedback_tail(topic: str, cfg, n_entries: int = 5) -> str:
    """Read the last N entries from feedback-{topic}.md (agent self-reflections)."""
    fb_path = Path(cfg["paths"]["lead_gen_root"]) / cfg["paths"]["feedback_template"].format(topic=topic)
    if not fb_path.exists():
        return "(no prior feedback file; first run for this topic)"

    text = fb_path.read_text()
    entries = text.split("\n## ")
    tail = entries[-n_entries:] if len(entries) > n_entries else entries
    if len(tail) > 1:
        return "## " + "\n## ".join(tail)
    return text


def _format_kb_patterns(patterns: dict | None) -> str:
    """Format kb.read_recent_patterns() output as a readable brief section.

    TODO(phase2): kb.read_recent_patterns(topic, days, cfg) is built in
    Phase 2. Expected schema (mirrors the legacy feedback-summary):
        {
          "window_days": 14,
          "stats": {"total_rated": int, "good": int, "bad": int},
          "patterns_detected": [str, ...],
          "high_yield_verticals": [{"vertical": str, "good": int, "bad": int, "examples": [str]}, ...],
          "saturated_verticals": [{"vertical": str, "good": int, "bad": int, "tags": [str], "examples": [str]}, ...],
          "region_distribution": [{"region": str, "good": int, "bad": int}, ...],
          "examples": {"good": [...], "bad": [...]}
        }
    """
    if not patterns:
        return ""
    if patterns.get("stats", {}).get("total_rated", 0) == 0:
        return (f"## Recent kb.md patterns\n\n"
                f"(no rated leads in the last {patterns.get('window_days', 14)}d; no learning signal yet)\n")

    lines = [f"## Recent kb.md patterns (last {patterns['window_days']}d, from your kb.md good/bad notes)"]
    lines.append("")
    s = patterns["stats"]
    lines.append(f"**Stats**: {s['total_rated']} rated total - {s['good']} good, {s['bad']} bad")
    lines.append("")

    if patterns.get("patterns_detected"):
        lines.append("**Patterns detected (act on these)**:")
        for p in patterns["patterns_detected"]:
            lines.append(f"- {p}")
        lines.append("")

    if patterns.get("high_yield_verticals"):
        lines.append("**High-yield verticals (lean into these)**:")
        for v in patterns["high_yield_verticals"]:
            ex = ", ".join(v["examples"][:3])
            lines.append(f"- `{v['vertical']}`: {v['good']}/{v['good']+v['bad']} good. Examples: {ex}")
        lines.append("")

    if patterns.get("saturated_verticals"):
        lines.append("**Saturated verticals (avoid these)**:")
        for v in patterns["saturated_verticals"]:
            ex = ", ".join(v["examples"][:3])
            tags = ", ".join(v.get("tags", [])[:5])
            lines.append(f"- `{v['vertical']}`: {v['bad']}/{v['good']+v['bad']} bad. Tags: {tags}. Examples: {ex}")
        lines.append("")

    if patterns.get("region_distribution"):
        lines.append("**Region distribution (good vs bad)**:")
        for r in patterns["region_distribution"][:6]:
            lines.append(f"- {r['region']}: {r['good']} good, {r['bad']} bad")
        lines.append("")

    good_ex = patterns.get("examples", {}).get("good", [])[:5]
    bad_ex = patterns.get("examples", {}).get("bad", [])[:5]
    if good_ex:
        lines.append("**Recent good ratings** (mirror these patterns):")
        for e in good_ex:
            tags = ", ".join(e.get("tags") or [])
            reason = e.get("reason") or "(no reason)"
            lines.append(f"- {e['company']} ({e.get('vertical') or '?'}, {e.get('region') or '?'}): {reason} [tags: {tags}]")
        lines.append("")
    if bad_ex:
        lines.append("**Recent bad ratings** (avoid these patterns):")
        for e in bad_ex:
            tags = ", ".join(e.get("tags") or [])
            reason = e.get("reason") or "(no reason)"
            lines.append(f"- {e['company']} ({e.get('vertical') or '?'}, {e.get('region') or '?'}): {reason} [tags: {tags}]")
        lines.append("")

    return "\n".join(lines)


def print_brief(topic: str, cfg, dry_run: bool = False) -> int:
    today = _today_myt()
    date_str = today.isoformat()
    letter, label = _day_type(today, cfg)
    candidates_path = (
        Path(cfg["paths"]["lead_gen_root"])
        / cfg["paths"]["candidates_template"].format(topic=topic, date=date_str)
    )

    topic_ref = SKILL_DIR / f"references/topics/{topic}.md"
    rotation_ref = SKILL_DIR / "references/discovery-rotation.md"
    scoring_ref = SKILL_DIR / "references/scoring-rubric.md"

    print(f"# Phase B Discovery Brief")
    print(f"**Topic**: {topic}")
    print(f"**Date**: {date_str} (MYT)")
    print(f"**Day-type**: {letter} ({label})")
    print(f"**Candidates target**: {cfg['candidate_target_per_topic']}")
    print(f"**Score floor**: {cfg['score_floor']}")
    print(f"**Per-topic ceiling**: {cfg['per_topic_ceiling']} (post-dedup)")
    print()
    print("## Reference reads (in order)")
    philosophy_ref = SKILL_DIR / "references/lead-philosophy.md"
    print(f"1. **Lead philosophy / Filter 0**: {philosophy_ref} — read FIRST. Filter 0 has two parts:")
    print(f"   - 0a: AI producer (customer-facing AI), not consumer (internal-only AI)")
    print(f"   - 0b: AI **aggregator** (uses third-party APIs), not **model builder** (owns proprietary model)")
    print(f"   Skip a candidate IMMEDIATELY if either filter fails — do not score them, do not ship them.")
    print(f"2. Topic ICP + search angles: {topic_ref}")
    print(f"3. Day-type method: {rotation_ref} (today: day-type {letter})")
    print(f"4. Scoring rubric: {scoring_ref}")
    print()
    print("## Filter 0 quick-check signals (apply during research)")
    print()
    print("**Skip on Filter 0a (consumer)**: AI is internal-only — marketing/sales/ops use ChatGPT/Midjourney internally; customer never sees AI output.")
    print()
    print("**Skip on Filter 0b (model builder)** — look for these signals on the candidate's site:")
    print("- 'proprietary model', 'we trained', 'our model', 'research-backed'")
    print("- arxiv links, research papers, academic team featured")
    print("- research-grant funding (NSF / NextGenerationEU / DARPA / Horizon Europe / NIH)")
    print("- Pricing tied to training compute or per-token training")
    print("- Open-source model weights / architecture")
    print("- They sell an API to OTHER businesses (i.e., they are a model provider)")
    print()
    print("**Keep (aggregator producer)** — these signals mean SHIP-ELIGIBLE:")
    print("- 'powered by [X]', 'integrated with [Y]', tech-stack page lists OpenAI/Anthropic/Stable Diffusion/etc.")
    print("- Application-layer focus: UI, workflow, vertical business logic")
    print("- Per-output / per-credit pricing (passes through API costs)")
    print("- Fast iteration cadence (not bottlenecked by model training)")
    print()
    print("If signals are mixed (e.g., uses third-party APIs but also claims a 'custom model'), default to **skip**. Ambiguity wastes time.")
    print()

    # Pull pattern signals from kb.md (your good/bad notes from prior shipments).
    # TODO(phase2): kb.read_recent_patterns is implemented in Phase 2.
    kb = _kb()
    patterns = None
    if kb is not None:
        try:
            patterns = kb.read_recent_patterns(topic, 14, cfg)
        except Exception as e:
            print(f"# (kb.read_recent_patterns unavailable: {e})", file=sys.stderr)
    formatted = _format_kb_patterns(patterns)
    if formatted:
        print(formatted)
        print()

    print("## Recent agent reflections (last 5 entries from feedback-{topic}.md)")
    print()
    print(_read_feedback_tail(topic, cfg))
    print()
    print("## Output target")
    print(f"Write candidates to: `{candidates_path}`")
    print()
    print("Format: JSON array of objects with keys:")
    print("  company, domain, topic, score, industry, region, employee_count,")
    print("  outreach_angle, discovered_via, rationale,")
    print("  producer_evidence, model_ownership")
    print()
    print("Field requirements:")
    print("  - **producer_evidence** (mandatory): 1 sentence citation that the candidate's customer sees AI output (URL fragment, app store listing, product page screenshot caption). If you cannot fill this, the candidate fails Filter 0a and must be skipped, not shipped.")
    print("  - **model_ownership** (mandatory): one of `aggregator` | `model_builder` | `unclear`. Only `aggregator` is ship-eligible. `model_builder` and `unclear` are skipped per Filter 0b.")
    print()
    print("Then exit Phase B. Phase C walks the dedup pipeline next.")

    if dry_run:
        print()
        print("[DRY-RUN] would not actually do research. Brief printed only.")

    return 0


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--topic", required=True,
                    help="Topic slug (validated against topic_registry at runtime).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    sys.path.insert(0, str(SCRIPT_DIR))
    from _config import load_config
    from topic_registry import get_topic, cfg_for_topic
    cfg = load_config()
    if get_topic(args.topic, cfg) is None:
        print(f"Unknown or disabled topic: {args.topic!r}", file=sys.stderr)
        sys.exit(2)
    sys.exit(print_brief(args.topic, cfg_for_topic(cfg, args.topic), dry_run=args.dry_run))
