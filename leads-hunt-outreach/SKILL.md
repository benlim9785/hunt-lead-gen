---
name: leads-hunt-outreach
description: "On-demand outreach drafting for a lead from the Lark Base `Leads` table, in the AE's voice. The host agent reads style.md fresh on every draft."
author: Ben Lim
license: MIT
---

# leads-hunt-outreach

Draft a cold outreach message for a single lead, in the AE's voice. **You (the host agent) do this directly in chat — no scripts, no external LLM calls.** The voice file is read fresh on every draft so style edits take effect immediately.

## When to invoke

The AE says one of:
- *"draft outreach for <company>"*
- *"write a cold message for <company>"*
- *"@<company> what would you say?"*
- *"reply to the digest, target row N"*

If the request is ambiguous about which lead, ask before drafting.

## Procedure (you do this directly, no scripts)

1. **Locate the lead row** from the AE's current data sources:
   - Primary source: the configured Lark Base `Leads` table (workspace wiring lives in `<workspace>/leads-hunt/config.json`).
   - If the AE said *"row N from today's digest"*: identify the company from today's aggregate CSV at `<workspace>/leads-hunt/data/lead-gen/leads-aggregate-YYYY-MM-DD.csv`, then use that row context.
   - If the AE named a company: match case-insensitively against the most relevant shipped lead record you can access.
   - If still ambiguous (multiple matches, or no clear digest), ask the AE to clarify (paste the row, give the exact company name, or specify a date).
   - If neither Base wiring nor any recent CSV exists, tell the AE the workspace is not fully set up yet and point them at `leads-hunt-setup`.

2. **Read the AE's voice** from `<workspace>/leads-hunt/style.md`. Pay attention to sections that drive drafting:
   - `## Rhythm & cadence` — how the AE writes: sentence length, hedges, punctuation quirks
   - `## Vocabulary do's and don'ts` — explicit allow/ban list
   - `## Real outreach samples` — real messages they have sent

   Heading names may vary slightly between versions of the voice file; match on intent, not exact string.

   If `style.md` is empty, missing, or has only placeholder text, draft in a flat, professional, low-fluff register and tell the AE:
   > *your style.md is empty — say `add this to my voice: <paste a real message>` to teach me your voice.*

3. **Draft the message** matching the voice. Constraints:
   - 60-120 words unless the AE specifies otherwise
   - Open with a specific reference to the lead's recent activity or fit signal from the lead record
   - Exactly one concrete CTA at the end (sandbox link / 15-min call / share a benchmark / reply with a question)
   - Match the AE's punctuation, capitalization, emoji, and hedge patterns from samples
   - Honor the `### Avoid` ban list exactly — if a banned phrase fits naturally, restructure
   - No invented facts: every product capability or proof point must come from `style.md`, the lead record, or explicitly provided user context. If a fact is not there, omit the claim.

4. **Reply in chat** with the draft, prefixed by a 1-line note in italics so the AE can tell at a glance what you read:

   > *Draft for Acme Corp (style.md: 4 samples, rhythm-set):*
   >
   > [the message body]

   Replace the parenthetical with what you actually loaded — e.g. `(style.md: empty, generic voice)` if no samples were available.

5. **Iterate** if the AE responds with edits. After 2–3 rounds, if a recurring correction emerges (e.g. *"always shorter"*, *"never use semicolons"*, *"don't open with 'hey'"*), suggest:

      > *want me to add this to your voice? say `add to my don'ts: semicolons` (or `add to my voice: <rule>`)*

   This routes to the `leads-hunt-voice` skill, which owns `style.md` edits.

## What you do NOT do

- Do **NOT** call any external LLM API. You ARE the LLM — draft inline.
- Do **NOT** invoke a script or subprocess for drafting; this skill is instruction-only.
- Do **NOT** write the draft to disk. It lives in the chat reply only.
- Do **NOT** modify `style.md` from this skill. `style.md` is owned by `leads-hunt-voice`.
- Do **NOT** treat `kb.md` as the runtime lead source. It is only a legacy compatibility notes file now.

## Worked example

AE: *"draft outreach for Acme Corp"*

You:
1. Read the relevant lead record from the configured Base `Leads` table or today's aggregate CSV. The row says: *"CEO posted on LinkedIn about migrating off Runway; BytePlus has comparable Seedance pricing."*
2. Read `<workspace>/leads-hunt/style.md` → AE's rhythm: short sentences, comma splices ok, no em-dashes, max 1 emoji, sample shows opener `hey, saw your...`. Ban list includes *"Hope this finds you well"*, *"reaching out"*.
3. Draft (in chat):

   > *Draft for Acme Corp (style.md: 4 samples, rhythm-set):*
   >
   > hey, saw your post about leaving runway. we have similar pricing on seedance with a free tier you can play with. happy to set up a sandbox if you want, takes 5 min.

If the AE replies *"shorter, drop the 'happy to'"*, revise inline and after the second similar correction offer to teach the voice file.

## Companion skills

- `leads-hunt` — owns the workspace, Lark Base wiring, lead discovery, scoring, and shipping.
- `leads-hunt-voice` — owns `style.md` (the AE's voice file). Use it when the AE wants to teach a new pattern or review what you'll read on the next draft.
