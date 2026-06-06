---
name: leads-hunt-outreach
description: "On-demand outreach drafting for a kb.md lead row, in the AE's voice. The host agent reads style.md fresh on every draft."
version: 0.2.0
author: Ben Lim
license: MIT
---

# leads-hunt-outreach

Draft a cold outreach message for a single lead, in the AE's voice. **You (the host agent) do this directly in chat — no scripts, no external LLM calls.** The voice file is read fresh on every draft so style edits take effect immediately.

## When to invoke

The AE says one of:
- *"draft outreach for &lt;company&gt;"*
- *"write a cold message for &lt;company&gt;"*
- *"@&lt;company&gt; what would you say?"*
- *"reply to the digest, target row N"*

If the request is ambiguous about which lead, ask before drafting.

## Procedure (you do this directly, no scripts)

1. **Locate the lead row** in `<workspace>/leads-hunt/kb.md` (default workspace: `~/.openclaw/workspace`):
   - If the AE named a company: find the H3 sub-section under `## Shipped Leads` whose heading matches that company (case-insensitive, allow partial match).
   - If the AE said *"row N from today's digest"*: read the most recent date H2 under `## Shipped Leads` and pick the Nth bullet/sub-section.
   - If still ambiguous (multiple matches, or no clear digest), ask the AE to clarify (paste the row, give the exact company name, or specify a date).
   - If kb.md is missing entirely, tell the AE the workspace isn't set up yet — point them at the `leads-hunt` skill to seed it.

2. **Read the AE's voice** from `<workspace>/leads-hunt/style.md`. Pay attention to sections that drive drafting:
   - `## Rhythm & cadence` (or `## Your voice rhythm`) — how the AE writes: sentence length, hedges, em-dash policy, punctuation tics
   - `## Vocabulary do's and don'ts` (or an `### Avoid` / banlist subsection) — explicit allow/banlist
   - `## Real outreach samples` (or `## Examples`) — paste blocks of messages they've sent

   Heading names vary between voice files; match on intent, not exact string.

   If style.md is empty, missing, or has only placeholder text (`[example message here]`, `_(empty — ...)_`), draft in a flat, professional, low-fluff register and tell the AE:
   > *your style.md is empty — say `add this to my voice: <paste a real message>` to teach me your voice.*

3. **Draft the message** matching the voice. Constraints:
   - 60-120 words unless the AE specifies otherwise
   - Open with a specific reference to the lead's recent activity (the kb.md row will have a `signal` / `why` field — use it)
   - Exactly one concrete CTA at the end (sandbox link / 15-min call / share a benchmark / reply with a question)
   - Match the AE's punctuation, capitalization, emoji, and hedge patterns from samples
   - Honor the `### Avoid` banlist exactly — if a banned phrase fits naturally, restructure
   - No invented facts: every product capability or proof URL must come from style.md or the kb row. If a fact isn't there, omit the claim.

4. **Reply in chat** with the draft, prefixed by a 1-line note in italics so the AE can tell at a glance what you read:

   > *Draft for Acme Corp (style.md: 4 samples, rhythm-set):*
   >
   > [the message body]

   Replace the parenthetical with what you actually loaded — e.g. `(style.md: empty, generic voice)` if no samples were available.

5. **Iterate** if the AE responds with edits. After 2–3 rounds, if a recurring correction emerges (e.g. *"always shorter"*, *"never use semicolons"*, *"don't open with 'hey'"*), suggest:

   > *want me to add this to your voice? say `add to my don'ts: semicolons` (or `add to my voice: <rule>`)*

   This routes to the `leads-hunt-voice` skill, which owns style.md edits.

## What you do NOT do

- Do **NOT** call any external LLM API. You ARE the LLM — draft inline.
- Do **NOT** invoke a script or subprocess for drafting; this skill is instruction-only.
- Do **NOT** write the draft to disk. It lives in the chat reply only.
- Do **NOT** modify `kb.md` or `style.md` from this skill. `kb.md` is owned by `leads-hunt`; `style.md` by `leads-hunt-voice`. Suggest the right skill if the AE asks for an edit.

## Worked example

AE: *"draft outreach for Acme Corp"*

You:
1. Read `~/.openclaw/workspace/leads-hunt/kb.md` → find `### Acme Corp` under the latest date heading. Row says: *"CEO posted on LinkedIn about migrating off Runway; BytePlus has comparable Seedance pricing."*
2. Read `~/.openclaw/workspace/leads-hunt/style.md` → AE's rhythm: short sentences, comma splices ok, no em-dashes, max 1 emoji, sample shows opener `hey, saw your...`. Banlist includes *"Hope this finds you well"*, *"reaching out"*.
3. Draft (in chat):

   > *Draft for Acme Corp (style.md: 4 samples, rhythm-set):*
   >
   > hey, saw your post about leaving runway. we have similar pricing on seedance with a free tier you can play with. happy to set up a sandbox if you want, takes 5 min.

If the AE replies *"shorter, drop the 'happy to'"*, revise inline and after the second similar correction offer to teach the voice file.

## Companion skills

- `leads-hunt` — owns the workspace and kb.md (lead discovery, scoring, shipping).
- `leads-hunt-voice` — owns style.md (the AE's voice file). Use it when the AE wants to teach a new pattern or review what you'll read on the next draft.
