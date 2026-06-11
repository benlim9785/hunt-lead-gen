#!/usr/bin/env python3
"""Lark Base sync helpers for leads-hunt.

Uses `lark-cli base` shortcuts (backed by the Lark Base/Bitable OpenAPI) so the
skill can read/write the AE's Base without storing extra app credentials.

The shared skill keeps defaults in `scripts/config.json`. Per-AE Base IDs and the
webhook URL live in `<LEADS_HUNT_HOME>/config.json`, which `_config.load_config()`
merges automatically.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _config import load_config  # noqa: E402


class LarkBaseConfigError(RuntimeError):
    pass


class LarkBaseCommandError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def _cfg_section(cfg: dict) -> dict:
    return cfg.get("lark_base") or {}


def is_configured(cfg: dict) -> bool:
    section = _cfg_section(cfg)
    tables = section.get("tables") or {}
    return bool(
        section.get("base_token")
        and (tables.get("leads") or {}).get("id")
        and (tables.get("skip_list") or {}).get("id")
        and (tables.get("discovery_patterns") or {}).get("id")
    )


def _require_base_cfg(cfg: dict) -> dict:
    if not is_configured(cfg):
        raise LarkBaseConfigError(
            "Lark Base is not configured. Run leads-hunt-setup Base creation first."
        )
    return _cfg_section(cfg)


def _table_cfg(cfg: dict, table_key: str) -> dict:
    section = _require_base_cfg(cfg)
    table = (section.get("tables") or {}).get(table_key) or {}
    if not table.get("id"):
        raise LarkBaseConfigError(f"Missing table id for lark_base.tables.{table_key}")
    return table


def _run_lark_cli(args: list[str]) -> dict[str, Any]:
    cmd = ["lark-cli", "base", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise LarkBaseCommandError(
            f"lark-cli failed (exit {proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {}
    start = stdout.find("{")
    if start > 0:
        stdout = stdout[start:]
    return json.loads(stdout)


def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = (payload or {}).get("data") or {}
    items = data.get("data") or data.get("items") or data.get("records") or []
    if isinstance(data.get("record"), dict):
        items = [data["record"]]
    records: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fields = item.get("fields") if isinstance(item.get("fields"), dict) else None
        if fields is None:
            fields = {
                k: v
                for k, v in item.items()
                if k not in {"record_id", "recordId", "id", "fields"}
            }
        records.append(
            {
                "record_id": item.get("record_id") or item.get("recordId") or item.get("id"),
                "fields": fields,
            }
        )
    return records


def _record_list(
    cfg: dict,
    table_key: str,
    *,
    field_ids: list[str] | None = None,
    filter_json: dict[str, Any] | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    table = _table_cfg(cfg, table_key)
    section = _require_base_cfg(cfg)
    cmd = [
        "+record-list",
        "--base-token",
        section["base_token"],
        "--table-id",
        table["id"],
        "--limit",
        str(limit),
        "--offset",
        str(offset),
        "--format",
        "json",
    ]
    for field in field_ids or []:
        cmd.extend(["--field-id", field])
    if filter_json:
        cmd.extend(["--filter-json", json.dumps(filter_json, ensure_ascii=False)])
    return _run_lark_cli(cmd)


def _record_get(
    cfg: dict,
    table_key: str,
    record_id: str,
    *,
    field_ids: list[str] | None = None,
) -> dict[str, Any]:
    table = _table_cfg(cfg, table_key)
    section = _require_base_cfg(cfg)
    cmd = [
        "+record-get",
        "--base-token",
        section["base_token"],
        "--table-id",
        table["id"],
        "--record-id",
        record_id,
        "--format",
        "json",
    ]
    for field in field_ids or []:
        cmd.extend(["--field-id", field])
    return _run_lark_cli(cmd)


def _record_upsert(
    cfg: dict,
    table_key: str,
    values: dict[str, Any],
    *,
    record_id: str | None = None,
) -> dict[str, Any]:
    table = _table_cfg(cfg, table_key)
    section = _require_base_cfg(cfg)
    cmd = [
        "+record-upsert",
        "--base-token",
        section["base_token"],
        "--table-id",
        table["id"],
        "--json",
        json.dumps(values, ensure_ascii=False),
    ]
    if record_id:
        cmd.extend(["--record-id", record_id])
    return _run_lark_cli(cmd)


def _iter_records(
    cfg: dict,
    table_key: str,
    *,
    field_ids: list[str] | None = None,
    filter_json: dict[str, Any] | None = None,
    page_size: int = 200,
) -> list[dict[str, Any]]:
    all_records: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = _record_list(
            cfg,
            table_key,
            field_ids=field_ids,
            filter_json=filter_json,
            limit=page_size,
            offset=offset,
        )
        data = payload.get("data") or {}
        records = _extract_records(payload)
        all_records.extend(records)
        if not data.get("has_more"):
            break
        offset += page_size
    return all_records


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "name", "value", "full_address"):
            if value.get(key) not in (None, ""):
                return _coerce_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_coerce_text(v) for v in value]
        return "\n".join([p for p in parts if p])
    return str(value)


def _normalize_date_string(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return ""
    if "T" in text:
        text = text.split("T", 1)[0]
    if " " in text:
        text = text.split(" ", 1)[0]
    return text


def _as_datetime_string(value: Any) -> str:
    date_str = _normalize_date_string(value)
    if not date_str:
        date_str = (datetime.utcnow()).date().isoformat()
    return f"{date_str} 00:00:00"


def _first_present(d: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = d.get(key)
        if value not in (None, "", []):
            return value
    return default


def _lead_payload(row: dict[str, Any]) -> dict[str, Any]:
    company = str(_first_present(row, "company", "Company")).strip()
    topic = str(_first_present(row, "topic", "Topic", "_topic")).strip()
    if not company:
        raise ValueError("Lead row is missing company")
    payload: dict[str, Any] = {
        "Company": company,
        "Topic": topic,
        "Date": _as_datetime_string(_first_present(row, "date", "Date")),
        "Draft Message": str(_first_present(row, "draft_message", default="No")) or "No",
        "Status": str(_first_present(row, "status", "Status", default="New")) or "New",
    }

    score = _first_present(row, "score", "Score", default=None)
    if score not in (None, ""):
        try:
            payload["Score"] = float(score)
        except (TypeError, ValueError):
            pass

    sales_nav_url = _first_present(row, "sales_nav_url", "Sales Nav URL", "SalesNavURL")
    linkedin_url = _first_present(row, "linkedin_url", "LinkedIn URL", "LinkedInURL")
    summary = _first_present(row, "summary", "Summary", "OutreachAngle")
    message_draft = _first_present(row, "message_draft", "Message Draft")

    if sales_nav_url:
        payload["Sales Nav URL"] = str(sales_nav_url)
    if linkedin_url:
        payload["LinkedIn URL"] = str(linkedin_url)
    if summary:
        payload["Summary"] = str(summary)
    if message_draft:
        payload["Message Draft"] = str(message_draft)
    return payload


def _lead_filter(company: str, topic: str, date_value: Any) -> dict[str, Any]:
    conditions: list[list[Any]] = [["Company", "==", company]]
    if topic:
        conditions.append(["Topic", "==", topic])
    date_str = _normalize_date_string(date_value)
    if date_str:
        conditions.append(["Date", "==", f"ExactDate({date_str})"])
    return {"logic": "and", "conditions": conditions}


def find_lead_record(cfg: dict, company: str, topic: str, date_value: Any) -> dict[str, Any] | None:
    records = _iter_records(
        cfg,
        "leads",
        field_ids=["Company", "Topic", "Date", "Status", "Draft Message", "Message Draft"],
        filter_json=_lead_filter(company, topic, date_value),
        page_size=50,
    )
    return records[0] if records else None


def upsert_lead(cfg: dict, row: dict[str, Any]) -> dict[str, Any]:
    payload = _lead_payload(row)
    existing = find_lead_record(cfg, payload["Company"], payload.get("Topic", ""), payload.get("Date", ""))
    record_id = existing.get("record_id") if existing else None
    return _record_upsert(cfg, "leads", payload, record_id=record_id)


def upsert_leads(cfg: dict, rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}
    for row in rows:
        company = str(_first_present(row, "company", "Company")).strip()
        if not company:
            summary["skipped"] += 1
            continue
        result = upsert_lead(cfg, row)
        summary["processed"] += 1
        data = result.get("data") or {}
        if data.get("created"):
            summary["created"] += 1
        elif data.get("updated"):
            summary["updated"] += 1
        else:
            summary["updated"] += 1
    return summary


def get_lead_record(cfg: dict, record_id: str) -> dict[str, Any]:
    payload = _record_get(
        cfg,
        "leads",
        record_id,
        field_ids=[
            "Company",
            "Topic",
            "Score",
            "Sales Nav URL",
            "LinkedIn URL",
            "Summary",
            "Draft Message",
            "Message Draft",
            "Date",
            "Status",
        ],
    )
    records = _extract_records(payload)
    if not records:
        raise LarkBaseCommandError(f"Lead record not found: {record_id}")
    return records[0]


def update_draft(cfg: dict, record_id: str, draft: str, *, draft_state: str = "Done") -> dict[str, Any]:
    values = {
        "Message Draft": draft,
        "Draft Message": draft_state,
    }
    return _record_upsert(cfg, "leads", values, record_id=record_id)


def read_skip_list(cfg: dict) -> set[str]:
    records = _iter_records(cfg, "skip_list", field_ids=["Domain/Company"], page_size=200)
    values: set[str] = set()
    for record in records:
        text = _coerce_text((record.get("fields") or {}).get("Domain/Company"))
        norm = _normalize(text)
        if norm:
            values.add(norm)
    return values


def write_discovery_pattern(
    cfg: dict,
    *,
    topic: str,
    good: str | list[str] = "",
    bad: str | list[str] = "",
    date_value: Any | None = None,
) -> dict[str, Any]:
    def _join(value: str | list[str]) -> str:
        if isinstance(value, list):
            return "\n".join([str(v).strip() for v in value if str(v).strip()])
        return str(value or "").strip()

    date_str = _normalize_date_string(date_value) or datetime.utcnow().date().isoformat()
    filter_json = {
        "logic": "and",
        "conditions": [
            ["Topic", "==", topic],
            ["Date", "==", f"ExactDate({date_str})"],
        ],
    }
    existing = _iter_records(
        cfg,
        "discovery_patterns",
        field_ids=["Date", "Topic", "Good", "Bad"],
        filter_json=filter_json,
        page_size=20,
    )
    values = {
        "Date": _as_datetime_string(date_str),
        "Topic": topic,
        "Good": _join(good),
        "Bad": _join(bad),
    }
    return _record_upsert(
        cfg,
        "discovery_patterns",
        values,
        record_id=existing[0].get("record_id") if existing else None,
    )


def _load_rows_arg(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.json_file:
        return json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    if args.json:
        return json.loads(args.json)
    raise SystemExit("provide --json or --json-file")


def _load_draft_arg(args: argparse.Namespace) -> str:
    if args.draft_file:
        return Path(args.draft_file).read_text(encoding="utf-8")
    if args.draft:
        return args.draft
    raise SystemExit("provide --draft or --draft-file")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", help="Override LEADS_HUNT_HOME (per-AE workspace)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status")

    upsert_parser = sub.add_parser("upsert-leads")
    upsert_parser.add_argument("--json")
    upsert_parser.add_argument("--json-file")

    get_parser = sub.add_parser("get-lead")
    get_parser.add_argument("--record-id", required=True)

    draft_parser = sub.add_parser("update-draft")
    draft_parser.add_argument("--record-id", required=True)
    draft_parser.add_argument("--draft")
    draft_parser.add_argument("--draft-file")
    draft_parser.add_argument("--draft-state", default="Done")

    sub.add_parser("read-skip-list")

    pattern_parser = sub.add_parser("write-discovery-pattern")
    pattern_parser.add_argument("--topic", required=True)
    pattern_parser.add_argument("--good", default="")
    pattern_parser.add_argument("--bad", default="")
    pattern_parser.add_argument("--date")

    args = parser.parse_args(argv)
    if args.home:
        os.environ["LEADS_HUNT_HOME"] = args.home
    cfg = load_config()

    if args.command == "status":
        out = {
            "configured": is_configured(cfg),
            "base_token": (_cfg_section(cfg).get("base_token") or ""),
            "tables": (_cfg_section(cfg).get("tables") or {}),
            "workspace_config": cfg.get("_workspace_config_path"),
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    try:
        if args.command == "upsert-leads":
            rows = _load_rows_arg(args)
            print(json.dumps(upsert_leads(cfg, rows), indent=2, ensure_ascii=False))
            return 0
        if args.command == "get-lead":
            print(json.dumps(get_lead_record(cfg, args.record_id), indent=2, ensure_ascii=False))
            return 0
        if args.command == "update-draft":
            draft = _load_draft_arg(args)
            print(
                json.dumps(
                    update_draft(cfg, args.record_id, draft, draft_state=args.draft_state),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "read-skip-list":
            values = sorted(read_skip_list(cfg))
            print(json.dumps(values, indent=2, ensure_ascii=False))
            return 0
        if args.command == "write-discovery-pattern":
            result = write_discovery_pattern(
                cfg,
                topic=args.topic,
                good=args.good,
                bad=args.bad,
                date_value=args.date,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0
    except (LarkBaseConfigError, LarkBaseCommandError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
