---
name: leads-hunt-outreach
description: "On-demand outreach drafting from a kb.md lead row + your voice file. Reads style.md fresh on every draft."
version: 0.1.0
author: Ben Lim
license: MIT
---

# Leads Hunt Outreach

Compose a cold outreach message for a lead in YOUR voice. Output **only the message body** — no preamble, no commentary, no character count. The textarea or chat receives raw output verbatim and that is what the customer sees.

## When to use

- CLI: `python3 scripts/draft.py <slug>` (or `--company <name>` for fuzzy match)
- Lark / chat: agent calls `python3 scripts/draft.py <slug>` directly via its terminal tool, then pastes the result back to you

The drafter routes through a single script (`scripts/draft.py`) — single source of truth for prompt + cleanup logic, no drift between surfaces.

## Voice file

Your voice file lives at `<workspace>/leads-hunt/style.md` (default: `~/.openclaw/workspace/leads-hunt/style.md`). Manage it conversationally via the `leads-hunt-voice` skill, or edit it directly. The drafter re-reads it fresh on every invocation, so changes take effect immediately — no restart, no rebuild.

If `<workspace>/leads-hunt/style.md` does not exist, the drafter falls back to the blank-slate template at `references/style.md` (this skill's own copy). Without examples, drafts will be generic — fill in your voice file before relying on output.

## Inputs

The script reads a lead row from `<workspace>/leads-hunt/kb.md` by slug (`kb.lookup(slug)`). Expected fields per lead row:

- `company_name`, `website`, `region`, `description`, `signal`, `source`
- `score` (0-10, optional)
- `contacts` (JSON array; pick first with email or linkedin → that's the PIC)
- `ceo_name` as PIC fallback

## Output structure

Five blocks in order — adapt phrasing to YOUR voice file, but keep the skeleton:

```
[1] Greeting:  Address the PIC by first name. Unknown name → generic greeting.

[2] Bridge:    1 sentence positioning who you are and previewing the value claim.

[3] Products:  1-3 numbered items (1. 2. 3., not bullets). Each tied to the
               lead's actual product, workflow, or vertical — never abstract.

[4] Demos:     0-2 demo URLs / proof points. Each on own line, with a 1-line
               label above. Pick vertical-fit URL from your voice file.

[5] Closer:    A short forward-looking line.
```

The exact wording of each block — greeting style, bridge phrasing, closer line, hedges, punctuation rhythm — comes from `style.md`. The drafter reads your voice file fresh every call.

## Hard rules

1. **No subject line** — textarea-only.
2. **No emoji** in cold outreach (unless your voice file explicitly opts in).
3. **No em-dashes (—) or en-dashes (–)** — they read as AI-tells. Use comma, hyphen-with-spaces, or restructure.
4. **No meta-commentary in output**: never emit "Character count: NNN", "Let me tighten", "Here is the draft:", code fences, or any reasoning/iteration trace. Verify silently, emit only the final body.
5. **No invented facts**: every product capability, sample URL, or proof point must come from the voice file or kb row. If a fact isn't there, omit the claim.

## Forbidden patterns (default; override in voice file if needed)

- "Hope this helps"
- "Let me know if you have any questions"
- "In summary" / "Overall"
- "Feel free to reach out"
- Generic openers: "I came across your company", "I noticed your business"
- AI-tells: "I'd be happy to...", "I think you'll find...", "I'm reaching out to...", "Just wanted to..."
- "I hope you don't mind..."

## Output contract

- Start the response with the greeting line directly. No preamble.
- End with the closer.
- **Nothing else.** No "Here is the draft:", no character count, no code fences, no explanation. The response IS the message.

## Pitfalls

- **Greeting cleanup:** the drafter runs a regex that finds the LAST greeting line followed by a blank line and trims everything before it. So if you accidentally emit reasoning prose, the script may still rescue it — but don't rely on this. Emit clean.
- **Sparse signal:** if the lead row has no `signal` and `description` is thin, fall back to a generic value claim from your voice file rather than inventing specifics.
- **Empty contacts:** when `contacts=[]` and no `ceo_name`, default to a generic greeting from your voice file. Never invent a name.
- **{SPECIFIC ASPECT} must be concrete:** "AI workflow" is too generic. Pull a specific phrase from the lead's actual description. If genuinely sparse, use the safest fallback in your voice file.

## Companion skill

`leads-hunt-voice` — manages `<workspace>/leads-hunt/style.md` via Lark chat. Use it to set your voice rhythm, add example messages, and review what the drafter will read on the next call.
