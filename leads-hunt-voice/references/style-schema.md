# style.md schema (the contract)

This is the canonical shape of `<workspace>/leads-hunt/style.md`. The `leads-hunt-outreach` skill reads this exact structure on every draft. The `leads-hunt-voice` skill is the only thing that should mutate it programmatically (you can also edit by hand).

Sections tagged `(used by drafting)` are consumed by the outreach pipeline. Everything else is for the AE's own reference and is ignored by the drafter.

---

```markdown
# AE outreach voice

This file teaches the leads-hunt-outreach skill how YOU write. The agent reads it before drafting any cold message and matches your idiom.

Edit freely. Sections marked `(used by drafting)` are read by the outreach pipeline; other sections are notes for yourself.

## Rhythm & cadence (used by drafting)

<freeform prose, 1-3 short paragraphs describing how the AE writes — sentence
length pattern, comma-splice tendencies, hedge usage, opener/closer style>

## Vocabulary do's and don'ts (used by drafting)

### Do use
- <one bullet per allowed phrase or word, with a brief why if useful>

### Avoid
- <one bullet per banned phrase, with reason — e.g. 'em-dash: never use, feels AI-generated'>

## Real outreach samples (used by drafting)

<paste-block format: each sample wrapped in a fenced block, dated, optionally annotated by the AE>

### 2026-05-20 — sent to Acme Corp CEO, replied within 4hrs
> hey, saw your blog post about migrating off runway. we have similar pricing and a free tier you can play with. happy to set up a sandbox if you want.

## Voice notes (NOT used by drafting; AE freeform notes)

<anything the AE wants to remember about their voice that isn't directly actionable for the model — e.g. 'when I'm tired I get too curt, watch for that'>
```

---

## Section-by-section notes

### `## Rhythm & cadence (used by drafting)`
Body is freeform prose. The drafter reads this verbatim and uses it as a style anchor. Replace via `voice.py set-rhythm`. Be concrete: "sentences <12 words, no semicolons, max one emoji per message" beats "be casual".

### `## Vocabulary do's and don'ts (used by drafting)`
Two `###` subsections under one `##`. The drafter reads both bullet lists and tries to honor them. Append bullets via `voice.py add-do <text>` / `voice.py add-dont <text>`. Idempotent — duplicates are skipped.

### `## Real outreach samples (used by drafting)`
The drafter's most important input. The model learns voice from examples better than from rules. Append samples via `voice.py add-sample --date YYYY-MM-DD [--annotation TEXT] --content -` (reads from stdin). Each sample becomes a `### YYYY-MM-DD — annotation` heading followed by a fenced block.

### `## Voice notes (NOT used by drafting; AE freeform notes)`
Ignored by the drafter. The AE can write whatever they want here — meta-observations, things to watch for, mood notes. The voice CLI does not currently mutate this section; edit by hand.

---

## Round-trip guarantees

After any `voice.py` write, the file MUST still parse correctly via `parse_section.read_section`. The CLI verifies this implicitly: `add-sample`, `set-rhythm`, `add-do`, `add-dont` all read the existing section, mutate, and replace atomically. If parsing breaks, the write fails and the original file is preserved.

## Empty-is-fine principle

Every section may be empty. The outreach drafter handles missing rhythm, zero samples, and empty do/don't lists gracefully — output is just less personalized. Voice quality grows with iteration; ship empty and improve.
