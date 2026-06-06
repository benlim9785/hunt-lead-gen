#!/usr/bin/env python3
"""
Phase D: aggregate per-topic CSVs and print the Lark digest to stdout.

The agent invoking this captures stdout and posts it to the AE's Lark
channel via the LARK_WEBHOOK_URL configured in `.env`. Lark renders
Markdown — bold, emoji, and code blocks all work.

Steps:
  1. Read per-topic CSVs at {LEADS_HUNT_HOME}/data/lead-gen/leads-{topic}-YYYY-MM-DD.csv
  2. Write aggregate CSV (sorted by Score desc).
  3. Print digest with top 5 + counts + CSV path.
  4. Append shipped leads to kb.md so future Phase C runs dedup against them.

Voice rules: no em-dash, light emoji only (⭐ 🌐 💡 📊 🔍 ⚠️ 📁 ✅).
"""
from __future__ import annotations

import csv
import datetime
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from write_csv import write_aggregate_csv  # noqa: E402


def _kb():
    """Lazy import of kb module (built in Phase 2)."""
    try:
        import kb  # type: ignore
        return kb
    except ImportError:
        return None


def _today_myt() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date().isoformat()


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def _topics_from_registry(cfg) -> list[str]:
    try:
        from topic_registry import enabled_topics
        return [t["slug"] for t in enabled_topics(cfg)]
    except Exception:
        # Fallback: discover from existing CSVs in lead_gen_root for today
        today = _today_myt()
        root = Path(cfg["paths"]["lead_gen_root"])
        prefix = "leads-"
        suffix = f"-{today}.csv"
        if not root.exists():
            return []
        out: list[str] = []
        for p in root.glob(f"{prefix}*{suffix}"):
            slug = p.name[len(prefix):-len(suffix)]
            if slug:
                out.append(slug)
        return out


def deliver(cfg, dry_run: bool = False) -> int:
    today = _today_myt()
    root = Path(cfg["paths"]["lead_gen_root"])
    topics = _topics_from_registry(cfg)
    per_topic_paths = {
        t: root / cfg["paths"]["csv_template"].format(topic=t, date=today)
        for t in topics
    }
    aggregate_path = root / cfg["paths"]["aggregate_csv_template"].format(date=today)

    if not dry_run:
        write_aggregate_csv(aggregate_path, list(per_topic_paths.values()))

    rows_by_topic = {t: _read_csv(p) for t, p in per_topic_paths.items()}
    total = sum(len(v) for v in rows_by_topic.values())

    if total == 0:
        print(_zero_leads_message(today, rows_by_topic, aggregate_path, topics))
        return 0

    # Combine + sort by score
    combined = []
    for t, rows in rows_by_topic.items():
        for r in rows:
            r["_topic"] = t
            combined.append(r)

    def score_key(r: dict) -> int:
        try:
            return int(r.get("Score", "0") or 0)
        except Exception:
            return 0

    combined.sort(key=score_key, reverse=True)
    top5 = combined[:5]

    print(_format_digest(today, top5, rows_by_topic, aggregate_path, topics))

    if not dry_run:
        # Append shipped leads to kb.md so Phase C can dedup against them on future runs.
        # kb.append_shipped(rows, today, cfg) writes shipped leads to kb.md.
        kb = _kb()
        if kb is not None:
            try:
                kb.append_shipped(combined, today, cfg)
            except Exception as e:
                print(f"[deliver] WARN: kb.append_shipped failed (non-fatal): {e}",
                      file=sys.stderr)
        else:
            print("[deliver] INFO: kb.py not yet available; shipped leads not logged "
                  "to kb.md (Phase 2 wires this in).", file=sys.stderr)
    return 0


def _format_digest(today: str, top5: list[dict], rows_by_topic: dict,
                   aggregate_path: Path, topics: list[str]) -> str:
    lines = []
    lines.append(f"🎯 *Lead Report ({today})*")
    lines.append("")

    # Count how many leads were not found in Sales Nav
    not_found_count = sum(1 for r in top5 if r.get("SalesNavNotFound") == "true")
    verified_count = sum(1 for r in top5 if r.get("SalesNavNotFound") != "true")
    if not_found_count == 0:
        lines.append("✅ All leads verified against Salesforce via Sales Nav (none in CRM).")
    else:
        if verified_count > 0:
            lines.append(f"✅ {verified_count} lead(s) verified via Sales Nav CRM.")
        lines.append(f"⚠️ {not_found_count} lead(s) not found in Sales Nav — CRM status unverified, manual check recommended.")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("*Top 5 by score:*")
    lines.append("")

    for i, r in enumerate(top5, 1):
        company = r.get("Company", "?")
        score = r.get("Score", "?")
        region = r.get("Region", "?")
        topic = r.get("_topic", r.get("Topic", ""))
        domain = r.get("Domain", "?")
        outreach = (r.get("OutreachAngle") or "").strip()
        if len(outreach) > 140:
            outreach = outreach[:137] + "..."
        lines.append(f"{i}. ⭐ {score}/10 *{company}* ({region}) ({topic})")
        lines.append(f"🌐 {domain}")
        if r.get("SalesNavNotFound") == "true":
            lines.append("⚠️ Not found in Sales Nav — manual CRM check needed")
        if outreach:
            lines.append(f"💡 {outreach}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    counts_line = ", ".join(f"{len(rows_by_topic.get(t, []))} {t}" for t in topics)
    lines.append(f"📊 {counts_line} = {sum(len(v) for v in rows_by_topic.values())} net-new today")
    lines.append("")
    lines.append("📁 Full CSV:")
    lines.append(str(aggregate_path))
    return "\n".join(lines)


def _zero_leads_message(today: str, rows_by_topic: dict, aggregate_path: Path,
                        topics: list[str]) -> str:
    parts = [f"🎯 *Lead Report ({today})*", ""]
    for t in topics:
        n = len(rows_by_topic.get(t, []))
        if n == 0:
            parts.append(f"⚠️ {t} ran dry today: 0 net-new after dedup.")
        else:
            parts.append(f"{t}: {n} leads (see CSV).")
    parts.append("")
    parts.append(f"📁 {aggregate_path}")
    return "\n".join(parts)


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    from _config import load_config
    cfg = load_config()
    sys.exit(deliver(cfg, dry_run=args.dry_run))
