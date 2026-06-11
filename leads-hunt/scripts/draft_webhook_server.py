#!/usr/bin/env python3
"""Inbound webhook server for leads-hunt Lark Base draft generation.

This exposes a small HTTP endpoint that Lark Base automation can call when a
lead row flips `Draft Message` to `Yes`.

Behavior:
- validates the webhook payload
- reads the latest lead row from the configured Lark Base
- reads `<LEADS_HUNT_HOME>/style.md` fresh on every request
- drafts a short outbound message using the row context + style hints
- writes the draft back to `Message Draft`
- sets `Draft Message` to `Done`

Stdlib-only by design so it can run in the AIME sandbox without extra deps.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import lark_base_sync  # noqa: E402
from _config import load_config, resolve_home  # noqa: E402

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
DEFAULT_PATH = "/leads-hunt/draft"
HEALTH_PATH = "/healthz"
MAX_BODY_BYTES = 256 * 1024
PLACEHOLDER_RE = re.compile(r"^_\(empty .*\)_$", re.IGNORECASE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "]",
    re.UNICODE,
)

LOGGER = logging.getLogger("leads_hunt.webhook")


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "name", "value", "full_address"):
            if value.get(key) not in (None, ""):
                return _coerce_text(value[key])
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [_coerce_text(item) for item in value]
        return "\n".join([p for p in parts if p]).strip()
    return str(value).strip()


def _first_present(d: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = _coerce_text(d.get(key))
        if value:
            return value
    return default


def _extract_heading_body(text: str, heading_prefix: str) -> str:
    lines = text.splitlines()
    start = None
    level = None
    for idx, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        hashes, title = match.groups()
        if line.strip() == heading_prefix.strip() or title.strip().lower() == heading_prefix.strip().lstrip("#").strip().lower():
            start = idx + 1
            level = len(hashes)
            break
    if start is None or level is None:
        return ""

    end = len(lines)
    for idx in range(start, len(lines)):
        match = HEADING_RE.match(lines[idx])
        if match and len(match.group(1)) <= level:
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def _extract_bullets(section_text: str, subheading: str) -> list[str]:
    body = _extract_heading_body(section_text, subheading)
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _strip_placeholder(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if PLACEHOLDER_RE.match(stripped):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _extract_sample_quotes(samples_text: str) -> list[str]:
    cleaned = _strip_placeholder(samples_text)
    if not cleaned:
        return []
    block_matches = re.findall(r"```\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
    samples = [m.strip() for m in block_matches if m.strip()]
    if samples:
        return samples

    quotes = []
    current: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            current.append(stripped.lstrip("> "))
        elif current:
            quotes.append(" ".join(current).strip())
            current = []
    if current:
        quotes.append(" ".join(current).strip())
    return [q for q in quotes if q]


def _style_meta(home: Path) -> dict[str, Any]:
    style_path = home / "style.md"
    if not style_path.exists():
        return {
            "path": str(style_path),
            "exists": False,
            "is_generic": True,
            "sample_count": 0,
            "rhythm": "",
            "dos": [],
            "donts": [],
            "samples": [],
        }

    text = style_path.read_text(encoding="utf-8")
    rhythm = _strip_placeholder(_extract_heading_body(text, "## Rhythm & cadence (used by drafting)"))
    vocab = _extract_heading_body(text, "## Vocabulary do's and don'ts (used by drafting)")
    samples_text = _extract_heading_body(text, "## Real outreach samples (used by drafting)")
    dos = [item for item in _extract_bullets(vocab, "### Do use") if item]
    donts = [item for item in _extract_bullets(vocab, "### Avoid") if item]
    samples = _extract_sample_quotes(samples_text)
    generic = not any([rhythm, dos, donts, samples])
    return {
        "path": str(style_path),
        "exists": True,
        "is_generic": generic,
        "sample_count": len(samples),
        "rhythm": rhythm,
        "dos": dos,
        "donts": donts,
        "samples": samples,
    }


def _style_flags(style: dict[str, Any]) -> dict[str, Any]:
    samples = style.get("samples") or []
    first_sample = samples[0] if samples else ""
    rhythm = (style.get("rhythm") or "").lower()
    donts = " ".join(style.get("donts") or []).lower()
    dos = " ".join(style.get("dos") or []).lower()
    joined_samples = "\n".join(samples)

    letters = [ch for ch in first_sample if ch.isalpha()]
    lowercase_ratio = 0.0
    if letters:
        lowercase_ratio = sum(1 for ch in letters if ch.islower()) / len(letters)

    opener = ""
    sample_start = first_sample.strip().split()
    if sample_start:
        first = sample_start[0].strip(",.!?:;").lower()
        if first in {"hey", "hi", "hello"}:
            opener = first

    allow_emoji = bool(EMOJI_RE.search(joined_samples)) or "emoji" in rhythm or "emoji" in dos
    no_em_dash = "em-dash" in donts or "em dash" in donts or "semicolon" in donts
    short = "short" in rhythm or "<12 words" in rhythm or "under 12" in rhythm or "brief" in rhythm

    return {
        "lowercase": lowercase_ratio >= 0.9,
        "opener": opener,
        "allow_emoji": allow_emoji,
        "no_em_dash": no_em_dash,
        "short_sentences": short,
    }


def _cleanup_phrase(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    return cleaned.strip(" .")


def _sentence(text: str) -> str:
    value = _cleanup_phrase(text)
    if not value:
        return ""
    return value[0].upper() + value[1:] + "."


def _apply_case(text: str, lowercase: bool) -> str:
    if not lowercase:
        return text
    return text.lower()


def _sanitize_avoidances(text: str, donts: list[str]) -> str:
    out = text
    replacements = {
        "hope this finds you well": "wanted to send a quick note",
        "reaching out": "sending a note",
        "touch base": "compare notes",
        "circle back": "follow up",
    }
    lowered = "\n".join(donts).lower()
    for phrase, replacement in replacements.items():
        if phrase in lowered:
            out = re.sub(re.escape(phrase), replacement, out, flags=re.IGNORECASE)
    if "em-dash" in lowered or "em dash" in lowered:
        out = out.replace("—", ",")
    return out


def _compose_message(row_fields: dict[str, Any], style: dict[str, Any]) -> str:
    company = _first_present(row_fields, "Company", "company") or "your team"
    topic = _first_present(row_fields, "Summary", "summary")
    fallback_topic = _first_present(row_fields, "Topic", "topic")
    style_flags = _style_flags(style)
    donts = style.get("donts") or []

    opener_parts: list[str] = []
    if style_flags["opener"]:
        opener_parts.append(f"{style_flags['opener']},")

    if topic:
        lowered_topic = topic.strip().lower()
        if re.match(r"^(saw|noticed|heard|read|watched)\b", lowered_topic):
            opener_parts.append(topic.strip())
        else:
            opener_parts.append(f"saw {topic}")
    elif fallback_topic:
        opener_parts.append(f"noticed {company} is leaning into {fallback_topic}")
    else:
        opener_parts.append(f"had {company} on my radar")

    opener = " ".join(opener_parts).strip(" ,")
    if opener.endswith("."):
        opener = opener[:-1]

    bridge = (
        f"thought it could be useful to compare notes on what {company} is seeing"
        if not fallback_topic
        else f"thought it might be worth a quick compare on {fallback_topic}"
    )

    cta = "Open to a quick 15 min chat next week?"

    sentences = [
        _sentence(opener),
        _sentence(bridge),
        cta,
    ]

    if style_flags["short_sentences"]:
        sentences = sentences[:3]
    text = " ".join([s for s in sentences if s]).strip()
    text = _sanitize_avoidances(text, donts)
    if style_flags["no_em_dash"]:
        text = text.replace("—", ",")
    if style_flags["allow_emoji"] and not style.get("is_generic"):
        text = text.rstrip() + " 🙂"
    text = _apply_case(text, style_flags["lowercase"])
    return text.strip()


def _style_label(style: dict[str, Any]) -> str:
    if style.get("is_generic"):
        return "style.md: empty, generic voice"
    samples = style.get("sample_count", 0)
    rhythm = "rhythm-set" if style.get("rhythm") else "rhythm-empty"
    return f"style.md: {samples} samples, {rhythm}"


def _process_payload(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if payload.get("event") != "leads_hunt_draft_requested":
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_event"}
    record_id = _coerce_text(payload.get("record_id"))
    if not record_id:
        return HTTPStatus.BAD_REQUEST, {"error": "missing_record_id"}
    table_name = _coerce_text(payload.get("table_name"))
    if table_name and table_name != "Leads":
        return HTTPStatus.BAD_REQUEST, {"error": "invalid_table_name", "table_name": table_name}

    cfg = load_config()
    section = (cfg.get("lark_base") or {})
    configured_base = _coerce_text(section.get("base_token"))
    configured_table = _coerce_text(((section.get("tables") or {}).get("leads") or {}).get("id"))

    payload_base = _coerce_text(payload.get("base_token"))
    payload_table = _coerce_text(payload.get("table_id"))
    if configured_base and payload_base and configured_base != payload_base:
        return HTTPStatus.BAD_REQUEST, {"error": "base_token_mismatch"}
    if configured_table and payload_table and configured_table != payload_table:
        return HTTPStatus.BAD_REQUEST, {"error": "table_id_mismatch"}

    record = lark_base_sync.get_lead_record(cfg, record_id)
    fields = record.get("fields") or {}
    draft_state = _first_present(fields, "Draft Message")
    existing_draft = _first_present(fields, "Message Draft")

    if draft_state == "Done" and existing_draft:
        return HTTPStatus.OK, {
            "accepted": True,
            "record_id": record_id,
            "status": "already_done",
        }
    if draft_state != "Yes":
        return HTTPStatus.OK, {
            "accepted": True,
            "record_id": record_id,
            "status": "noop_draft_state",
            "draft_state": draft_state,
        }

    home = resolve_home()
    style = _style_meta(home)
    draft = _compose_message(fields, style)
    lark_base_sync.update_draft(cfg, record_id, draft, draft_state="Done")
    return HTTPStatus.OK, {
        "accepted": True,
        "record_id": record_id,
        "status": "draft_written",
        "style": _style_label(style),
        "draft": draft,
    }


class WebhookHandler(BaseHTTPRequestHandler):
    server_version = "LeadsHuntWebhook/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == HEALTH_PATH:
            home = resolve_home()
            cfg = load_config()
            section = cfg.get("lark_base") or {}
            payload = {
                "ok": True,
                "service": "leads-hunt draft webhook",
                "home": str(home),
                "configured": bool(section.get("base_token")),
                "style_exists": (home / "style.md").exists(),
                "config_exists": (home / "config.json").exists(),
            }
            self._send_json(HTTPStatus.OK, payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != DEFAULT_PATH:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        content_length = self.headers.get("Content-Length", "0")
        try:
            body_len = int(content_length)
        except ValueError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if body_len <= 0 or body_len > MAX_BODY_BYTES:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_body_size"})
            return

        raw = self.rfile.read(body_len)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
            return

        try:
            status, response = _process_payload(payload)
        except Exception as exc:  # pragma: no cover - defensive runtime logging
            record_id = _coerce_text(payload.get("record_id"))
            LOGGER.exception("failed to process webhook for record_id=%s", record_id)
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"accepted": False, "record_id": record_id, "error": str(exc)},
            )
            return

        self._send_json(status, response)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--log-level", default=os.environ.get("LEADS_HUNT_WEBHOOK_LOG_LEVEL", "INFO"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    httpd = ThreadingHTTPServer((args.host, args.port), WebhookHandler)
    LOGGER.info("starting leads-hunt webhook server on %s:%s", args.host, args.port)
    LOGGER.info("draft endpoint: %s", DEFAULT_PATH)
    LOGGER.info("health endpoint: %s", HEALTH_PATH)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("shutting down webhook server")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
