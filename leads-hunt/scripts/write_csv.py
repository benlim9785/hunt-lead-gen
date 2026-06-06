#!/usr/bin/env python3
"""
Write per-topic or aggregate CSV.

Used by Phase C (per-topic) via dedup_pipeline.py and by Phase D for aggregate.
This module exposes both functions; can also be run as a CLI for ad-hoc use.

Header: Company,Domain,Topic,Score,Industry,Region,EmployeeCount,InCRM,SalesforceURL,OutreachAngle,DiscoveredVia,ProducerEvidence,SalesNavNotFound
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

COLUMNS = [
    "Company", "Domain", "Topic", "Score", "Industry", "Region",
    "EmployeeCount", "InCRM", "SalesforceURL", "OutreachAngle", "DiscoveredVia",
    "ProducerEvidence", "SalesNavNotFound",
]


def _row_from_dict(c: dict, topic_default: str = "") -> dict:
    return {
        "Company": c.get("company") or c.get("Company") or "",
        "Domain": c.get("domain") or c.get("Domain") or "",
        "Topic": c.get("topic") or c.get("Topic") or topic_default,
        "Score": c.get("score") if "score" in c else c.get("Score", ""),
        "Industry": c.get("industry") or c.get("Industry") or "",
        "Region": c.get("region") or c.get("Region") or "",
        "EmployeeCount": c.get("employee_count") or c.get("EmployeeCount") or "",
        "InCRM": "true" if c.get("in_crm") or (c.get("InCRM", "").lower() == "true") else "false",
        "SalesforceURL": c.get("salesforce_url") or c.get("SalesforceURL") or "",
        "OutreachAngle": c.get("outreach_angle") or c.get("OutreachAngle") or "",
        "DiscoveredVia": c.get("discovered_via") or c.get("DiscoveredVia") or "",
        "ProducerEvidence": c.get("producer_evidence") or c.get("ProducerEvidence") or "",
        "SalesNavNotFound": "true" if c.get("sales_nav_not_found") or (c.get("SalesNavNotFound", "").lower() == "true") else "false",
    }


def write_topic_csv(path: Path, rows: list[dict], topic: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(_row_from_dict(r, topic_default=topic))


def write_aggregate_csv(path: Path, sources: list[Path]) -> int:
    """Concatenate sources sorted by Score desc; return row count written."""
    all_rows: list[dict] = []
    for src in sources:
        if not src.exists():
            continue
        with src.open() as f:
            for row in csv.DictReader(f):
                all_rows.append(row)

    def score_key(r: dict) -> int:
        try:
            return int(r.get("Score", "0") or 0)
        except Exception:
            return 0

    all_rows.sort(key=score_key, reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
    return len(all_rows)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["topic", "aggregate"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--topic", default="")
    ap.add_argument("--sources", nargs="*", default=[])
    args = ap.parse_args()
    if args.mode == "topic":
        rows = json.loads(sys.stdin.read())
        write_topic_csv(Path(args.out), rows, args.topic)
    else:
        n = write_aggregate_csv(Path(args.out), [Path(s) for s in args.sources])
        print(f"wrote {n} rows to {args.out}")
