#!/usr/bin/env python3
"""
draft.py — generate cold outreach for a lead in the AE's voice.

Reads:
  - lead row from <LEADS_HUNT_HOME>/kb.md (by slug)
  - voice file from <LEADS_HUNT_HOME>/style.md (fallback: references/style.md
    blank template shipped with this skill)
  - skill protocol from this skill's SKILL.md

Calls the configured LLM provider directly (no hermes/agent subprocess).

Usage:
  python3 draft.py <slug>                       # by kb.md slug
  python3 draft.py --company "Dreamwave"        # fuzzy match on company_name
  python3 draft.py <slug> --json                # JSON output
  python3 draft.py <slug> --home /custom/path   # override workspace home

Exit codes: 0=ok, 1=lead not found, 2=LLM call failed, 3=config error.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# --- paths -------------------------------------------------------------------

SKILL_DIR = Path(__file__).resolve().parent.parent  # scripts/ -> skill root


def leads_hunt_home(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    workspace = os.environ.get(
        "OPENCLAW_WORKSPACE", os.path.expanduser("~/.openclaw/workspace")
    )
    return Path(workspace).expanduser().resolve() / "leads-hunt"


# --- kb.md lookup ------------------------------------------------------------

# TODO(phase2): replace this stub with `from kb import lookup` once kb.py
# (the shared kb.md reader) lands in the leads-hunt-pack.
def kb_lookup(home: Path, slug: str) -> dict | None:
    """
    Stub kb.md row reader. Phase 2 will provide a proper kb.py module.

    For now: parse a very simple frontmatter-per-row layout where each lead is
    a markdown section starting with `## <slug>` followed by a YAML-ish block.
    Returns dict or None.
    """
    kb_path = home / "kb.md"
    if not kb_path.exists():
        return None
    text = kb_path.read_text(encoding="utf-8")
    # Split on `## ` headings
    sections = re.split(r"(?m)^##\s+", text)
    for sec in sections[1:]:
        head, _, body = sec.partition("\n")
        row_slug = head.strip().split()[0] if head.strip() else ""
        if row_slug.lower() != slug.lower():
            continue
        row: dict = {"slug": row_slug}
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]?\s*([A-Za-z_][\w_]*)\s*:\s*(.+?)\s*$", line)
            if m:
                row[m.group(1)] = m.group(2)
            if line.startswith("## "):
                break
        return row
    return None


def kb_search_company(home: Path, name: str) -> list[dict]:
    """Fuzzy search kb.md for company_name matches."""
    kb_path = home / "kb.md"
    if not kb_path.exists():
        return []
    text = kb_path.read_text(encoding="utf-8")
    sections = re.split(r"(?m)^##\s+", text)
    hits: list[dict] = []
    for sec in sections[1:]:
        head, _, body = sec.partition("\n")
        row_slug = head.strip().split()[0] if head.strip() else ""
        row: dict = {"slug": row_slug}
        for line in body.splitlines():
            m = re.match(r"^\s*[-*]?\s*([A-Za-z_][\w_]*)\s*:\s*(.+?)\s*$", line)
            if m:
                row[m.group(1)] = m.group(2)
        company = (row.get("company_name") or "").lower()
        if name.lower() in company:
            hits.append(row)
    return hits


def find_lead_by_company(home: Path, name: str) -> dict:
    hits = kb_search_company(home, name)
    if not hits:
        print(f"error: no kb.md lead matches '{name}'", file=sys.stderr)
        sys.exit(1)
    exact = [r for r in hits if (r.get("company_name") or "").lower() == name.lower()]
    if exact:
        return exact[0]
    if len(hits) == 1:
        return hits[0]
    print(f"error: ambiguous '{name}', matches:", file=sys.stderr)
    for r in hits[:5]:
        print(f"  {r.get('slug')}  {r.get('company_name')}", file=sys.stderr)
    sys.exit(1)


# --- voice + skill loading ---------------------------------------------------

def load_voice(home: Path) -> str:
    """Read style.md fresh on every call. Workspace copy wins; fall back to
    the blank template that ships with this skill."""
    workspace_voice = home / "style.md"
    if workspace_voice.exists():
        return workspace_voice.read_text(encoding="utf-8")
    skill_voice = SKILL_DIR / "references" / "style.md"
    if skill_voice.exists():
        return skill_voice.read_text(encoding="utf-8")
    return ""


def load_protocol() -> str:
    skill_md = SKILL_DIR / "SKILL.md"
    return skill_md.read_text(encoding="utf-8") if skill_md.exists() else ""


# --- facts block -------------------------------------------------------------

def build_facts(lead: dict) -> str:
    contacts_raw = lead.get("contacts") or "[]"
    try:
        contacts = json.loads(contacts_raw) if isinstance(contacts_raw, str) else contacts_raw
    except Exception:
        contacts = []
    pic = next(
        (c for c in contacts if isinstance(c, dict) and c.get("name") and (c.get("email") or c.get("linkedin"))),
        None,
    )
    pic_name = (pic or {}).get("name") or lead.get("ceo_name") or ""
    pic_role = (pic or {}).get("role") or ("CEO" if lead.get("ceo_name") else "")

    rows = [
        f"Company: {lead.get('company_name', '')}",
        f"Website: {lead['website']}" if lead.get("website") else "",
        f"Region: {lead['region']}" if lead.get("region") else "",
        f"About: {lead['description']}" if lead.get("description") else "",
        f"Fit signal: {lead['signal']}" if lead.get("signal") else "",
        f"Source: {lead['source']}" if lead.get("source") else "",
        f"Score: {lead['score']}/10" if lead.get("score") else "",
        (
            f"PIC (Person In Charge to address): {pic_name}"
            + (f" ({pic_role})" if pic_role else "")
        )
        if pic_name
        else "PIC: unknown — use a generic greeting",
    ]
    return "\n".join(r for r in rows if r)


# --- LLM call ----------------------------------------------------------------

def call_llm(protocol: str, voice: str, facts: str) -> str:
    """
    Call the configured LLM provider to draft the message.

    TODO: AE configures LLM provider in .env. Defaults to OpenAI if
    OPENAI_API_KEY is set; otherwise prints config error.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("LEADS_HUNT_MODEL", "gpt-4o")

    if not api_key:
        print(
            "error: no LLM API key found. Set OPENAI_API_KEY (or configure your "
            "provider) in your .env / environment.",
            file=sys.stderr,
        )
        sys.exit(3)

    system_prompt = (
        "You are a cold-outreach drafter. Follow the SKILL PROTOCOL exactly. "
        "Match the VOICE FILE's rhythm, openers, hedges, and closers. Output "
        "ONLY the final message body — no preamble, no commentary, no "
        "character count, no code fences. Start with the greeting line "
        "directly.\n\n"
        f"--- SKILL PROTOCOL ---\n{protocol}\n\n"
        f"--- VOICE FILE ---\n{voice}\n"
    )
    user_prompt = f"Lead facts:\n{facts}\n\nDraft the outreach message now."

    try:
        # Lazy import so the script still parses without the SDK installed.
        from openai import OpenAI  # type: ignore
    except ImportError:
        print(
            "error: openai package not installed. `pip install openai` "
            "or configure a different provider.",
            file=sys.stderr,
        )
        sys.exit(3)

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
    except Exception as e:
        print(f"error: LLM call failed: {e}", file=sys.stderr)
        sys.exit(2)

    return clean_draft(text)


# --- post-processing ---------------------------------------------------------

def clean_draft(text: str) -> str:
    """Strip preamble / code fences / find the real greeting line."""
    text = text.strip()

    # Strip code fences (```...```)
    text = re.sub(r"^```[\w]*\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Find LAST "Hi/Hey <Word>[,!]" line followed by blank line → real greeting
    lines = text.split("\n")
    greeting_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        line = lines[i]
        if re.match(r"^(Hi|Hey|Hello)\s+[A-Z][\wÀ-ſ\s]*[,!]\s*$", line) or re.match(
            r"^(Hi|Hey|Hello)\s+(there|team)[,!]\s*$", line, re.I
        ):
            if i + 1 < len(lines) and lines[i + 1].strip() == "":
                greeting_idx = i
                break
    if greeting_idx > 0:
        text = "\n".join(lines[greeting_idx:]).strip()

    # Strip leftover preambles
    text = re.sub(r"^(Here['’]s|Here is)[^\n]*draft[^\n]*\n+", "", text, flags=re.I).strip()
    text = re.sub(r"^Draft:\s*\n+", "", text, flags=re.I).strip()
    text = re.sub(r"^\s*```[\w]*\s*\n?|```\s*$", "", text).strip()
    return text


# --- main --------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Draft outreach for a leads-hunt lead.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("slug", nargs="?", help="kb.md slug")
    g.add_argument("--company", help="fuzzy match by company_name")
    ap.add_argument("--home", help="override leads-hunt workspace home")
    ap.add_argument("--json", action="store_true", help="output JSON {draft, slug, company_name}")
    args = ap.parse_args()

    home = leads_hunt_home(args.home)
    if not home.exists():
        print(
            f"error: leads-hunt home not found at {home}. Set OPENCLAW_WORKSPACE "
            "or pass --home.",
            file=sys.stderr,
        )
        sys.exit(3)

    # Lookup lead
    if args.company:
        lead = find_lead_by_company(home, args.company)
    else:
        lead = kb_lookup(home, args.slug)
        if not lead:
            print(f"error: slug '{args.slug}' not found in {home}/kb.md", file=sys.stderr)
            sys.exit(1)

    # Load voice + protocol fresh on every call
    voice = load_voice(home)
    protocol = load_protocol()
    facts = build_facts(lead)

    draft = call_llm(protocol, voice, facts)
    if not draft:
        print("error: LLM returned empty draft", file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(
            json.dumps(
                {
                    "slug": lead.get("slug"),
                    "company_name": lead.get("company_name"),
                    "draft": draft,
                }
            )
        )
    else:
        print(draft)


if __name__ == "__main__":
    main()
