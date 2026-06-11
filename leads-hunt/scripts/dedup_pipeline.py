#!/usr/bin/env python3
"""
Phase C: walk the 3-layer dedup pipeline for a topic.

Inputs:
  candidates JSON at {lead_gen_root}/candidates/{topic}-YYYY-MM-DD.json (Phase B output)

Dedup layers (in order):
  Layer 1: same-day skip — candidate already shipped earlier today
           (kb.already_seen reads kb.md "shipped" log; same-day re-runs of Phase C
           don't re-emit yesterday's candidates)
  Layer 2: skip-list.txt + Lark Base Skip List — domain or company name
           (manual + auto-grown, across both local file state and shared Base state)
  Layer 3: LLM-judge against kb.md — historical "have we shipped this before?"
           via kb.already_seen normalised name match. kb.md is the source of
           truth for "have we engaged this company before". Phase D appends
           every shipped lead via kb.append_shipped().
  Layer 4: Sales Nav CRM check (sales_nav_check.check) — BD-team-wide CRM
           coverage. Catches leads worked by other BD reps outside this skill.

Outputs:
  {lead_gen_root}/leads-{topic}-YYYY-MM-DD.csv      (per-topic, ≤5 ship-eligible rows)
  {lead_gen_root}/run-log-YYYY-MM-DD.txt            (appended phase log)
  {lead_gen_root}/sales-nav-cache.jsonl             (extended via sales_nav_check)
  {LEADS_HUNT_HOME}/skip-list.txt                   (appended with new CRM hits)

Exit codes:
  0  normal completion
  1  fatal error
"""
from __future__ import annotations

import csv
import datetime
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from sales_nav_check import check as sales_nav_check  # noqa: E402

# kb.py is imported lazily inside
# functions so that the module is importable even before kb.py exists, and
# we degrade gracefully when it's missing.


def _kb():
    """Lazy import of kb module (built in Phase 2)."""
    try:
        import kb  # type: ignore
        return kb
    except ImportError:
        return None


def _base_sync():
    """Lazy import of Lark Base sync helper."""
    try:
        import lark_base_sync  # type: ignore
        return lark_base_sync
    except ImportError:
        return None


def _today_myt() -> str:
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).date().isoformat()


def _normalize(s: str) -> str:
    """Strip to lowercase alphanumeric only (no spaces, no punctuation).

    This makes 'GammaTime', 'Gamma Time', and 'gamma time' all collapse to
    'gammatime', preventing spacing/punctuation mismatches from causing
    duplicate leads to slip through dedup.
    """
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load_skip_list(cfg) -> set[str]:
    out: set[str] = set()
    p = Path(cfg["paths"]["skip_list"])
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.add(_normalize(line))

    base_sync = _base_sync()
    if base_sync is not None:
        try:
            if base_sync.is_configured(cfg):
                out.update(base_sync.read_skip_list(cfg))
        except Exception as e:
            print(
                f"[dedup] WARN: failed to read Lark Base Skip List: {e}; continuing with local skip-list only",
                file=sys.stderr,
            )
    return out


def _kb_already_seen(name: str, cfg) -> bool:
    """Layer 3: LLM-judge against kb.md historical shipments.

    kb.py provides already_seen(name, cfg) -> bool that walks
    kb.md's "## Shipped" section, normalises company names, and returns True
    if the candidate has been shipped before. For now, returns False (no-op)
    if kb module isn't built yet — Phase C still runs but Layer 3 is a pass-through.
    """
    kb = _kb()
    if kb is None:
        return False
    try:
        return bool(kb.already_seen(name, cfg))
    except Exception as e:
        print(f"[dedup] WARN: kb.already_seen({name!r}) failed: {e}; treating as not-seen",
              file=sys.stderr)
        return False


def _append_skip_list(cfg, entries: list[tuple[str, str]]) -> None:
    if not entries:
        return
    p = Path(cfg["paths"]["skip_list"])
    p.parent.mkdir(parents=True, exist_ok=True)
    today = _today_myt()
    lines = [f"\n# auto-skip from {today} dedup run"]
    for name, reason in entries:
        lines.append(f"{name}  # {reason}")
    with p.open("a") as f:
        f.write("\n".join(lines) + "\n")


def _log(msg: str, cfg) -> None:
    today = _today_myt()
    log_path = Path(cfg["paths"]["lead_gen_root"]) / cfg["paths"]["run_log_template"].format(date=today)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with log_path.open("a") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)


def run_dedup(topic: str, cfg, dry_run: bool = False) -> int:
    today = _today_myt()
    candidates_path = (
        Path(cfg["paths"]["lead_gen_root"])
        / cfg["paths"]["candidates_template"].format(topic=topic, date=today)
    )
    if not candidates_path.exists():
        _log(f"[Phase C/{topic}] ERROR: candidates file missing at {candidates_path}", cfg)
        return 1

    candidates = json.loads(candidates_path.read_text())
    if not isinstance(candidates, list):
        _log(f"[Phase C/{topic}] ERROR: candidates JSON is not an array", cfg)
        return 1

    _log(f"[Phase C/{topic}] starting dedup over {len(candidates)} candidates", cfg)
    # 3-layer dedup stack:
    #   Layer 2 (skip-list + Base Skip List) — cheapest, in-memory set
    #   Layer 3 (kb.md)                      — historical shipments, source of truth
    #   Layer 4 (Sales Nav)                  — personal Sales Nav session check; if unavailable,
    #                         continue and flag rows for manual CRM review
    skip_set = _load_skip_list(cfg)

    survivors: list[dict] = []
    new_skip_entries: list[tuple[str, str]] = []
    counts = {"layer2": 0, "layer3": 0, "layer4_in_crm": 0, "layer4_not_in_crm": 0,
              "score_below": 0, "shipped": 0, "errors": 0}

    for c in candidates:
        name = c.get("company") or ""
        domain = (c.get("domain") or "").lower().strip()
        nname = _normalize(name)

        if not name:
            counts["errors"] += 1
            continue

        if nname in skip_set or (domain and _normalize(domain) in skip_set):
            counts["layer2"] += 1
            _log(f"  SKIP layer2 (skip-list): {name}", cfg)
            continue
        if _kb_already_seen(name, cfg):
            counts["layer3"] += 1
            _log(f"  SKIP layer3 (kb.md: previously shipped): {name}", cfg)
            continue

        if dry_run:
            _log(f"  [dry-run] would Layer 4 query: {name}", cfg)
            survivors.append(c)
            continue

        result = sales_nav_check(name, cfg)
        layer4_unverified = False
        if result.get("error") == "sso-expired":
            _log(f"  layer4 session-expired (Sales Nav): {name} — including, flagged for manual review", cfg)
            counts["layer4_not_in_crm"] += 1
            c["sales_nav_not_found"] = True
            layer4_unverified = True
        elif result.get("error") == "not-found":
            # Company not in Sales Nav — can't confirm CRM status, but not a reason to drop.
            # Treat as not-in-CRM and let it through; flag in digest for manual review.
            _log(f"  layer4 not-found (Sales Nav): {name} — including, flagged for manual review", cfg)
            counts["layer4_not_in_crm"] += 1
            c["sales_nav_not_found"] = True
            layer4_unverified = True
        elif result.get("error"):
            _log(f"  WARN layer4 error for {name}: {result.get('error')}", cfg)
            counts["errors"] += 1
            continue
        elif result.get("in_crm"):
            counts["layer4_in_crm"] += 1
            new_skip_entries.append((name, f"sales-nav: in CRM"))
            _log(f"  SKIP layer4 (Sales Nav: in CRM): {name}", cfg)
            continue

        if not layer4_unverified:
            counts["layer4_not_in_crm"] += 1
        # Apply final score floor
        score = int(c.get("score", 0))
        if score < cfg.get("score_floor", 8):
            counts["score_below"] += 1
            _log(f"  SKIP score<{cfg['score_floor']}: {name} (score {score})", cfg)
            continue

        c.setdefault("in_crm", False)
        survivors.append(c)
        if len(survivors) >= cfg["per_topic_ceiling"]:
            _log(f"  reached per-topic ceiling ({cfg['per_topic_ceiling']}); stopping", cfg)
            break

    counts["shipped"] = len(survivors)
    _append_skip_list(cfg, new_skip_entries)
    _write_csv(topic, today, survivors, cfg)
    _log(f"[Phase C/{topic}] DONE counts={json.dumps(counts)}", cfg)
    return 0


def _first_present(d: dict, *keys, default=""):
    """Return first non-empty value for any of the given keys."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return default


def _normalize_domain(value: str) -> str:
    """Strip scheme + www. and trailing slash from a URL or domain."""
    if not value:
        return ""
    v = str(value).strip().lower()
    for prefix in ("https://", "http://"):
        if v.startswith(prefix):
            v = v[len(prefix):]
    if v.startswith("www."):
        v = v[4:]
    return v.rstrip("/").split("/")[0]


def _normalize_region(value: str) -> str:
    """Best-effort country extraction from 'City, ST, Country' format strings."""
    if not value:
        return ""
    s = str(value).strip()
    # Last comma-separated segment is usually the country
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if not parts:
        return s
    last = parts[-1]
    # Map common forms
    mapping = {
        "USA": "US", "United States": "US", "U.S.": "US", "U.S.A.": "US", "US": "US",
        "United Kingdom": "UK", "UK": "UK",
        "France": "FR", "Germany": "DE", "Netherlands": "NL", "Spain": "ES",
        "Italy": "IT", "Sweden": "SE", "Norway": "NO", "Denmark": "DK", "Finland": "FI",
        "Israel": "IL", "India": "IN",
        "Singapore": "SG", "Indonesia": "ID", "Vietnam": "VN", "Thailand": "TH",
        "Malaysia": "MY", "Philippines": "PH",
        "Brazil": "BR", "Mexico": "MX", "Argentina": "AR",
        "Australia": "AU", "Canada": "CA",
    }
    return mapping.get(last, last)


def _write_csv(topic: str, today: str, rows: list[dict], cfg) -> None:
    out_path = (
        Path(cfg["paths"]["lead_gen_root"])
        / cfg["paths"]["csv_template"].format(topic=topic, date=today)
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "Company", "Domain", "Topic", "Score", "Industry", "Region",
        "EmployeeCount", "InCRM", "SalesforceURL", "OutreachAngle", "DiscoveredVia",
        "ProducerEvidence", "SalesNavNotFound",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            domain = _normalize_domain(_first_present(r, "domain", "website", "url"))
            region = _first_present(r, "region", "country")
            if not region:
                region = _normalize_region(_first_present(r, "hq", "city", "location"))
            w.writerow({
                "Company": _first_present(r, "company", "name"),
                "Domain": domain,
                "Topic": topic,
                "Score": r.get("score", ""),
                "Industry": _first_present(r, "industry", "vertical", "icp_vertical"),
                "Region": region,
                "EmployeeCount": _first_present(r, "employee_count", "employees", "employee_range"),
                "InCRM": "false" if not r.get("in_crm") else "true",
                "SalesforceURL": _first_present(r, "salesforce_url", "salesforceURL"),
                "OutreachAngle": _first_present(r, "outreach_angle", "pitch_angle", "pitch", "angle"),
                "DiscoveredVia": _first_present(r, "discovered_via", "source", "discoveredVia"),
                "ProducerEvidence": _first_present(r, "producer_evidence", "ai_producer_evidence", "producer_proof"),
                "SalesNavNotFound": "true" if r.get("sales_nav_not_found") else "false",
            })


if __name__ == "__main__":
    import argparse
    import os
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True,
                    help="Topic slug (validated against topic_registry at runtime).")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace).")
    args = ap.parse_args()
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    from _config import load_config
    from topic_registry import get_topic, cfg_for_topic
    cfg = load_config()
    if get_topic(args.topic, cfg) is None:
        print(f"Unknown or disabled topic: {args.topic!r}", file=sys.stderr)
        sys.exit(2)
    sys.exit(run_dedup(args.topic, cfg_for_topic(cfg, args.topic), dry_run=args.dry_run))
