#!/usr/bin/env python3
"""Create and configure the leads-hunt Lark Base for one AE workspace.

What it does:
  1. Creates a new Base named `leads-hunt` (or a caller-provided name)
  2. Creates the 4 tables used by the skill
  3. Deletes the blank starter table that Lark creates by default
  4. Optionally creates + enables the webhook workflow when a webhook URL is supplied
  5. Saves the Base token, table IDs, URL, and workflow metadata to
     `<workspace>/leads-hunt/config.json`

The workspace config is intentionally separate from the shared skill defaults so
per-AE Base IDs do not leak into the installed skill package.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BASE_SCHEMA = [
    {
        "key": "leads",
        "name": "Leads",
        "fields": [
            {"name": "Company", "type": "text"},
            {"name": "Topic", "type": "text"},
            {
                "name": "Score",
                "type": "number",
                "style": {
                    "type": "plain",
                    "precision": 2,
                    "percentage": False,
                    "thousands_separator": False,
                },
            },
            {"name": "Sales Nav URL", "type": "text", "style": {"type": "url"}},
            {"name": "LinkedIn URL", "type": "text", "style": {"type": "url"}},
            {"name": "Summary", "type": "text"},
            {
                "name": "Draft Message",
                "type": "select",
                "multiple": False,
                "options": [
                    {"name": "Yes", "hue": "Orange", "lightness": "Light"},
                    {"name": "No", "hue": "Gray", "lightness": "Light"},
                    {"name": "Done", "hue": "Green", "lightness": "Light"},
                ],
            },
            {"name": "Message Draft", "type": "text"},
            {"name": "Date", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
            {
                "name": "Status",
                "type": "select",
                "multiple": False,
                "options": [
                    {"name": "New", "hue": "Blue", "lightness": "Lighter"},
                    {"name": "Contacted", "hue": "Wathet", "lightness": "Light"},
                    {"name": "Replied", "hue": "Green", "lightness": "Light"},
                    {"name": "Skipped", "hue": "Gray", "lightness": "Light"},
                ],
            },
        ],
    },
    {
        "key": "customers",
        "name": "Customers",
        "fields": [
            {"name": "Company", "type": "text"},
            {
                "name": "Status",
                "type": "select",
                "multiple": False,
                "options": [
                    {"name": "Active", "hue": "Green", "lightness": "Light"},
                    {"name": "Churned", "hue": "Gray", "lightness": "Light"},
                    {"name": "Prospect", "hue": "Blue", "lightness": "Lighter"},
                ],
            },
            {"name": "Date Added", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
        ],
    },
    {
        "key": "skip_list",
        "name": "Skip List",
        "fields": [
            {"name": "Domain/Company", "type": "text"},
            {"name": "Reason", "type": "text"},
            {"name": "Date Added", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
        ],
    },
    {
        "key": "discovery_patterns",
        "name": "Discovery Patterns",
        "fields": [
            {"name": "Date", "type": "datetime", "style": {"format": "yyyy-MM-dd"}},
            {"name": "Topic", "type": "text"},
            {"name": "Good", "type": "text"},
            {"name": "Bad", "type": "text"},
        ],
    },
]

WORKFLOW_NAME = "Generate outreach draft when Draft Message = Yes"
DEFAULT_WEBHOOK_ENV_KEYS = (
    "AIME_LEADS_HUNT_WEBHOOK_URL",
    "LEADS_HUNT_AIME_WEBHOOK_URL",
)


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    env = os.environ.get("AIME_WORKSPACE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path.cwd().resolve()


def _leads_home(workspace: Path) -> Path:
    return workspace / "leads-hunt"


def _workspace_config_path(workspace: Path) -> Path:
    return _leads_home(workspace) / "config.json"


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    stdout = (proc.stdout or "").strip()
    if not stdout:
        return {}
    start = stdout.find("{")
    if start > 0:
        stdout = stdout[start:]
    return json.loads(stdout)


def _base_cli(*args: str) -> dict[str, Any]:
    return _run(["lark-cli", "base", *args])


def _load_existing_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _extract_workflow_id(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    workflow = data.get("workflow") if isinstance(data.get("workflow"), dict) else {}
    for candidate in (
        workflow.get("id"),
        workflow.get("workflow_id"),
        data.get("workflow_id"),
        data.get("id"),
    ):
        if candidate:
            return str(candidate)
    return ""


def _build_workflow_body(*, webhook_url: str, base_token: str, leads_table_id: str) -> dict[str, Any]:
    prefix = (
        '{"event":"leads_hunt_draft_requested",'
        f'"base_token":"{base_token}",'
        f'"table_id":"{leads_table_id}",'
        '"table_name":"Leads",'
        '"record_id":"'
    )
    suffix = '","message_field":"Message Draft","draft_toggle_field":"Draft Message"}'
    return {
        "client_token": str(int(time.time() * 1000)),
        "title": WORKFLOW_NAME,
        "steps": [
            {
                "id": "step_trigger",
                "type": "SetRecordTrigger",
                "title": "When Draft Message becomes Yes",
                "next": "step_call_aime_webhook",
                "data": {
                    "table_name": "Leads",
                    "record_watch_conjunction": "and",
                    "field_watch_info": [
                        {
                            "field_name": "Draft Message",
                            "operator": "is",
                            "value": [{"value_type": "option", "value": {"name": "Yes"}}],
                        }
                    ],
                    "trigger_control_list": [],
                    "condition_list": None,
                },
            },
            {
                "id": "step_call_aime_webhook",
                "type": "HTTPClientAction",
                "title": "Call AIME draft webhook",
                "data": {
                    "method": "POST",
                    "url": [{"value_type": "text", "value": webhook_url}],
                    "headers": [
                        {
                            "key": "Content-Type",
                            "value": [{"value_type": "text", "value": "application/json"}],
                        }
                    ],
                    "body_type": "raw",
                    "raw_body": [
                        {"value_type": "text", "value": prefix},
                        {"value_type": "ref", "value": "$.step_trigger.recordId"},
                        {"value_type": "text", "value": suffix},
                    ],
                    "response_type": "json",
                    "response_value": '{"accepted":true}',
                },
            },
        ],
    }


def _webhook_url_from_args(args: argparse.Namespace) -> str:
    if args.webhook_url:
        return args.webhook_url.strip()
    for key in DEFAULT_WEBHOOK_ENV_KEYS:
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Override AIME_WORKSPACE_PATH")
    parser.add_argument("--base-name", default="leads-hunt")
    parser.add_argument(
        "--webhook-url",
        help="Inbound AIME webhook endpoint to call when Leads.Draft Message becomes Yes",
    )
    parser.add_argument(
        "--force-new-base",
        action="store_true",
        help="Create a fresh Base even if <workspace>/leads-hunt/config.json already has one",
    )
    args = parser.parse_args()

    workspace = resolve_workspace(args.workspace)
    home = _leads_home(workspace)
    home.mkdir(parents=True, exist_ok=True)
    config_path = _workspace_config_path(workspace)
    existing = _load_existing_config(config_path)
    existing_base = (existing.get("lark_base") or {}).get("base_token")
    if existing_base and not args.force_new_base:
        print(json.dumps({
            "created": False,
            "reason": "workspace config already has lark_base.base_token",
            "workspace_config": str(config_path),
            "lark_base": existing.get("lark_base") or {},
        }, indent=2, ensure_ascii=False))
        return 0

    webhook_url = _webhook_url_from_args(args)
    base_create = _base_cli("+base-create", "--name", args.base_name)
    base_info = (base_create.get("data") or {}).get("base") or {}
    base_token = base_info.get("base_token") or ""
    if not base_token:
        raise RuntimeError(f"Could not read base_token from base-create result: {base_create}")

    created_tables: dict[str, dict[str, str]] = {}
    desired_table_names = {spec["name"] for spec in BASE_SCHEMA}
    for spec in BASE_SCHEMA:
        resp = _base_cli(
            "+table-create",
            "--base-token",
            base_token,
            "--name",
            spec["name"],
            "--fields",
            json.dumps(spec["fields"], ensure_ascii=False),
        )
        table = (resp.get("data") or {}).get("table") or {}
        created_tables[spec["key"]] = {
            "id": str(table.get("id") or ""),
            "name": str(table.get("name") or spec["name"]),
        }

    listed = _base_cli("+table-list", "--base-token", base_token)
    for table in ((listed.get("data") or {}).get("tables") or []):
        table_id = str(table.get("id") or "")
        table_name = str(table.get("name") or "")
        if table_id and table_name not in desired_table_names:
            _base_cli(
                "+table-delete",
                "--base-token",
                base_token,
                "--table-id",
                table_id,
                "--yes",
            )

    workflow_meta = {
        "name": WORKFLOW_NAME,
        "id": "",
        "enabled": False,
    }
    if webhook_url:
        workflow_body = _build_workflow_body(
            webhook_url=webhook_url,
            base_token=base_token,
            leads_table_id=created_tables["leads"]["id"],
        )
        workflow_create = _base_cli(
            "+workflow-create",
            "--base-token",
            base_token,
            "--json",
            json.dumps(workflow_body, ensure_ascii=False),
        )
        workflow_id = _extract_workflow_id(workflow_create)
        if not workflow_id:
            raise RuntimeError(
                f"Workflow create succeeded but no workflow id was returned: {workflow_create}"
            )
        _base_cli(
            "+workflow-enable",
            "--base-token",
            base_token,
            "--workflow-id",
            workflow_id,
        )
        workflow_meta = {
            "name": WORKFLOW_NAME,
            "id": workflow_id,
            "enabled": True,
        }

    new_config = _deep_merge(
        existing,
        {
            "lark_base": {
                "base_token": base_token,
                "url": str(base_info.get("url") or ""),
                "webhook_url": webhook_url,
                "tables": created_tables,
                "workflow": {
                    "draft_message_yes": workflow_meta,
                },
            }
        },
    )
    config_path.write_text(json.dumps(new_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "created": True,
                "workspace_config": str(config_path),
                "lark_base": new_config["lark_base"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
