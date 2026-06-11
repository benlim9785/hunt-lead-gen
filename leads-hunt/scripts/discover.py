#!/usr/bin/env python3
"""
Phase B: print a discovery brief for the topic.

This script does NOT do the actual web research (that's the agent's job).
It prepares a "brief" the agent reads at start of Phase B:

  - today's day-type and method
  - last 5 entries from feedback-{topic}.md (per-topic agent reflections)
  - recent Lark Base discovery patterns (good/bad signals from prior shipments)
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
    """Format discovery-pattern output as a readable brief section."""
    if not patterns:
        return ""

    if patterns.get("stats"):
        if patterns.get("stats", {}).get("total_rated", 0) == 0:
            return (
                f"## Recent discovery patterns\n\n"
                f"(no rated leads in the last {patterns.get('window_days', 14)}d; no learning signal yet)\n"
            )

        lines = [
            f"## Recent discovery patterns (last {patterns['window_days']}d, from your Discovery Patterns Base table)"
        ]
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

    window_days = patterns.get("window_days", 14)
    good = patterns.get("good") or []
    bad = patterns.get("bad") or []
    entry_count = patterns.get("entry_count", 0)
    if not good and not bad:
        return (
            f"## Recent discovery patterns\n\n"
            f"(no Discovery Patterns rows found for `{patterns.get('topic', '')}` in the last {window_days}d)\n"
        )

    lines = [
        f"## Recent discovery patterns (last {window_days}d, from your Discovery Patterns Base table)",
        "",
    ]
    if entry_count:
        lines.append(f"**Entries reviewed**: {entry_count}")
        lines.append("")
    if good:
        lines.append("**Good signals to lean into:**")
        for value in good[:10]:
            lines.append(f"- {value}")
        lines.append("")
    if bad:
        lines.append("**Bad signals to avoid:**")
        for value in bad[:10]:
            lines.append(f"- {value}")
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

    # Pull pattern signals from the Discovery Patterns Base table.
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


# ---------------------------------------------------------------------------
# Fan-out mode (Phase B parallel sub-agent dispatch)
# ---------------------------------------------------------------------------
#
# In `brief` mode (the original behaviour), this script prints ONE topic's
# brief and the parent agent does the research itself, sequentially across
# topics. That serializes the parent's context window and accumulates per-topic
# browser/search noise.
#
# In `fanout-prompt` mode, this script prints a SINGLE master prompt which
# tells the parent agent to spawn N sub-agents (one per enabled topic) using
# `delegate_task`. Each sub-agent gets exactly one topic's brief inline and
# writes its own candidates JSON. The parent stays clean and runs Phase C
# dedup once all sub-agents return.
#
# The script itself never calls delegate_task — it just emits the prompt that
# instructs the agent to do so.


def _render_brief_string(topic_slug: str, cfg) -> str:
    """Capture print_brief() output for a single topic as a string.
    Uses stdout redirection so print_brief stays byte-identical to the
    original `brief` mode behaviour.
    """
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_brief(topic_slug, cfg, dry_run=False)
    return buf.getvalue()


# Max sub-agents per delegate_task call. The agent runtime caps concurrent
# fan-out at 3, so larger topic registries must be issued as multiple
# sequential delegate_task calls of <= 3 tasks each.
_FANOUT_BATCH_CAP = 3


def _fanout_task_block(topic_slug: str, brief_md: str) -> str:
    """Render a single delegate_task entry (Python dict literal, indented)."""
    # Triple-quoted string in the prompt — escape any embedded triple quotes
    # in the brief so the literal we emit is valid Python.
    safe_brief = brief_md.replace('"""', '\\"\\"\\"')
    return (
        '  {\n'
        f'    "goal": "Phase B discovery for topic \'{topic_slug}\': research, surface 10-20 candidates, write JSON to disk.",\n'
        f'    "context": """{safe_brief}""",\n'
        '    "toolsets": ["web", "browser", "terminal", "file"]\n'
        '  }'
    )


def _batch(items: list, n: int) -> list[list]:
    return [items[i:i + n] for i in range(0, len(items), n)]


def emit_fanout_prompt(cfg, enabled_topics: list[dict]) -> str:
    """Build the master prompt that tells the parent agent to fan out
    Phase B research across N sub-agents via delegate_task.

    Args:
        cfg: full config dict (from _config.load_config()).
        enabled_topics: list of topic dicts (from topic_registry.enabled_topics()).
                        Each must have a 'slug' key.

    Returns:
        A single multi-line string the agent will receive verbatim.
    """
    sys.path.insert(0, str(SCRIPT_DIR))
    from topic_registry import cfg_for_topic  # local import to avoid circulars

    n = len(enabled_topics)
    slugs = [t["slug"] for t in enabled_topics]
    batches = _batch(slugs, _FANOUT_BATCH_CAP)
    n_batches = len(batches)

    lines: list[str] = []
    lines.append("You are running leads-hunt Phase B discovery in fan-out mode.")
    lines.append("")
    lines.append(
        f"There are {n} enabled topics: {', '.join(slugs)}. "
        f"Spawn {n} sub-agents in parallel via `delegate_task`."
    )
    lines.append("Each sub-agent gets exactly ONE topic's brief and is responsible for:")
    lines.append("  - doing the web research (Brave search, browser navigation, vendor blog scraping)")
    lines.append("  - producing a candidates JSON list (10-20 candidates per topic)")
    lines.append("  - writing the JSON to <LEADS_HUNT_HOME>/data/lead-gen/candidates/<topic-slug>-<YYYY-MM-DD>.json")
    lines.append("  - returning a one-line summary for the parent agent (e.g. 'aigc-visual: 14 candidates written')")
    lines.append("")
    lines.append("## Concurrency / batching")
    lines.append("")
    lines.append(
        f"The agent runtime caps concurrent fan-out at {_FANOUT_BATCH_CAP} sub-agents per "
        "`delegate_task` call. With "
        f"{n} topics that means **{n_batches} sequential `delegate_task` call(s)**, each "
        f"with up to {_FANOUT_BATCH_CAP} tasks."
    )
    lines.append("")
    lines.append(
        "Do NOT collapse to a single sub-agent doing all topics — the parallelism is the point. "
        "Do NOT skip topics. Issue all batches before moving on to Phase C."
    )
    lines.append("")
    lines.append("## delegate_task call shape")
    lines.append("")
    lines.append(
        "Use this exact call shape for each batch (Python pseudocode — adapt to your "
        "agent harness's actual API):"
    )
    lines.append("")

    # Emit each batch as a separate delegate_task code block, with the brief
    # for each topic inlined verbatim as the sub-agent's `context`.
    for batch_i, batch_slugs in enumerate(batches, start=1):
        if n_batches > 1:
            lines.append(f"### Batch {batch_i} of {n_batches} ({len(batch_slugs)} task(s))")
            lines.append("")
        lines.append("```python")
        lines.append("delegate_task(tasks=[")
        task_blocks = []
        for slug in batch_slugs:
            topic_cfg = cfg_for_topic(cfg, slug)
            brief_md = _render_brief_string(slug, topic_cfg)
            task_blocks.append(_fanout_task_block(slug, brief_md))
        lines.append(",\n".join(task_blocks))
        lines.append("])")
        lines.append("```")
        lines.append("")

    lines.append("## After fan-out completes")
    lines.append("")
    lines.append("Once ALL sub-agents have returned (across all batches), each topic's")
    lines.append("candidates JSON should be on disk at the paths above. Then YOU (the parent)")
    lines.append("run Phase C dedup yourself — do NOT delegate this:")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/run_topic.py --phase dedup-all")
    lines.append("```")
    lines.append("")
    lines.append(
        "If any sub-agent reports failure (no JSON written, fewer than 5 candidates, "
        "tool errors), surface that in your final summary to the user but still proceed "
        "with Phase C on the topics that did succeed."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=["brief", "fanout-prompt"], default="brief",
                    help="brief: print a single topic's brief (default, current behaviour). "
                         "fanout-prompt: print a master prompt that drives the parent agent "
                         "to spawn one delegate_task sub-agent per enabled topic.")
    ap.add_argument("--topic",
                    help="Topic slug (required in --mode brief; ignored in --mode fanout-prompt).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    sys.path.insert(0, str(SCRIPT_DIR))
    from _config import load_config
    from topic_registry import get_topic, cfg_for_topic, enabled_topics
    cfg = load_config()

    if args.mode == "fanout-prompt":
        topics = enabled_topics(cfg)
        if not topics:
            print("No enabled topics found in topic_registry.", file=sys.stderr)
            sys.exit(2)
        sys.stdout.write(emit_fanout_prompt(cfg, topics))
        sys.stdout.write("\n")
        sys.exit(0)

    # mode == "brief": original behaviour, byte-identical.
    if not args.topic:
        print("--topic is required in --mode brief", file=sys.stderr)
        sys.exit(2)
    if get_topic(args.topic, cfg) is None:
        print(f"Unknown or disabled topic: {args.topic!r}", file=sys.stderr)
        sys.exit(2)
    sys.exit(print_brief(args.topic, cfg_for_topic(cfg, args.topic), dry_run=args.dry_run))
