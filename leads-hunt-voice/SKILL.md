---
name: leads-hunt-voice
description: "Teaches the leads-hunt-outreach skill the AE's writing voice. Update style.md conversationally via Lark — add samples, set rhythm, manage do's/don'ts. Drives sibling skill leads-hunt-outreach."
version: 0.1.0
author: Ben Lim
license: MIT
---

# leads-hunt-voice

A conversational editor for the AE's writing voice. Use this skill whenever the AE wants to **teach, refine, or review** how they write outreach. Sibling skill `leads-hunt-outreach` *reads* the resulting `style.md` on every draft; this skill *writes* it.

## What "voice" means here

This is **writing voice** — sentence rhythm, vocabulary, hedges, em-dash usage, emoji discipline, punctuation quirks, opener/closer patterns. **Not** a TTS / speech voice. The drafter reads `style.md` before generating any cold message and matches the AE's idiom.

## File layout

The voice file lives at `<workspace>/leads-hunt/style.md`. Workspace root resolves from the `LEADS_HUNT_HOME` env var (default `~/.openclaw/workspace/leads-hunt`). Both this skill and `leads-hunt-outreach` agree on this path.

The schema (canonical contract — see `references/style-schema.md`):

```markdown
# AE outreach voice

## Rhythm & cadence (used by drafting)
<freeform prose>

## Vocabulary do's and don'ts (used by drafting)
### Do use
- <bullet>
### Avoid
- <bullet>

## Real outreach samples (used by drafting)
### YYYY-MM-DD — annotation
```
<one real outreach message>
```

## Voice notes (NOT used by drafting; AE freeform notes)
<private prose>
```

Sections tagged `(used by drafting)` are read by the outreach pipeline. `Voice notes` is ignored by the drafter — it's the AE's scratchpad.

## When to invoke this skill

Trigger on any of the conversational patterns below. Don't ask the AE which subcommand they want — pick the right script call from their phrasing.

| AE says (example phrasings) | What to do |
|---|---|
| "add this to my voice: ..." / "add this sample" + paste | call `add-sample` (ask for today's date if not implied; default to today) |
| "set my voice rhythm: ..." / "my rhythm is ..." | call `set-rhythm` (replaces the section body) |
| "add to my do's: ..." / "I always say ..." | call `add-do` |
| "add to my don'ts: ..." / "never say ..." / "I never use ..." | call `add-dont` |
| "show my voice" / "what does my voice look like" / "read my style" | call `show`, paste output back to chat |
| "reset my voice" / "start over" | confirm **twice**, then call `reset --confirm-twice` |
| "clean up my voice" / "consolidate my style" | read style.md, propose a deduped version inline, ask AE to approve, then write via the relevant subcommands |

## Helper scripts

All scripts live in `scripts/`. Run with `python3 scripts/voice.py <subcmd>`. They respect `LEADS_HUNT_HOME`.

```
voice.py init [--force]                            # write empty skeleton
voice.py show                                       # print style.md
voice.py add-sample --date YYYY-MM-DD [--annotation T] --content -    # stdin → fenced sample block
voice.py set-rhythm --content -                     # stdin → replace Rhythm body
voice.py add-do "<phrase>"                          # bullet under Do use
voice.py add-dont "<phrase>"                        # bullet under Avoid
voice.py reset --confirm-twice                      # backup + write blank skeleton
```

All writes are atomic (tempfile + fsync + `os.replace`). `add-do`, `add-dont`, and `add-sample` are idempotent — duplicates are skipped with a one-line note. `set-rhythm` is always replace. `reset` saves `style.md.bak-<timestamp>` first, so recovery is always possible.

## Worked examples

### Example 1 — adding a sample

**AE in Lark:**
> add this to my voice (sent today, got a meeting):
> hey — saw your post on rebuilding nyt's email pipeline. we have a managed kafka tier with similar guarantees but no ops burden. want me to wire up a 1hr POC?

**Agent action:**
```bash
echo 'hey — saw your post on rebuilding nyt'"'"'s email pipeline. we have a managed kafka tier with similar guarantees but no ops burden. want me to wire up a 1hr POC?' \
  | python3 scripts/voice.py add-sample --date 2026-06-06 --annotation "got a meeting" --content -
```

**Diff in `style.md`** (under `## Real outreach samples (used by drafting)`):
```diff
+### 2026-06-06 — got a meeting
+
+```
+hey — saw your post on rebuilding nyt's email pipeline. we have a managed kafka tier with similar guarantees but no ops burden. want me to wire up a 1hr POC?
+```
```

Reply to AE: *"Added that sample (2026-06-06, 'got a meeting'). You now have N samples in your voice file."*

### Example 2 — banning a phrase

**AE in Lark:**
> never use em-dashes, they feel ai-generated

**Agent action:**
```bash
python3 scripts/voice.py add-dont "em-dash: never use, feels AI-generated"
```

**Diff** (under `### Avoid`):
```diff
+- em-dash: never use, feels AI-generated
```

Reply: *"Got it — added to your don'ts."* (and *don't* use an em-dash in the reply).

### Example 3 — setting rhythm

**AE in Lark:**
> set my rhythm: short sentences, max 12 words. comma splices ok. one emoji max per message. open with lowercase 'hey,' — never 'hi'.

**Agent action:**
```bash
echo "Short sentences, max 12 words. Comma splices ok. One emoji max per message. Open with lowercase 'hey,' — never 'hi'." \
  | python3 scripts/voice.py set-rhythm --content -
```

**Diff** (under `## Rhythm & cadence (used by drafting)`):
```diff
-_(empty — describe sentence length, hedges, opener/closer style, punctuation quirks. Or ask Clawdia: "set my voice rhythm: ...")_
+
+Short sentences, max 12 words. Comma splices ok. One emoji max per message. Open with lowercase 'hey,' — never 'hi'.
+
```

Reply: *"Rhythm updated. Run any draft now and it'll match."*

## Empty-is-fine principle

The pack ships `style.md` empty (just headings + placeholder italic notes). The outreach drafter handles every section being empty — output is just less personalized. Voice quality grows with iteration. Don't pressure the AE to fill it out all at once; encourage them to start by pasting 2-3 real samples and let rules emerge from feedback (see `references/iteration-tips.md`).

## Hard rules

1. **Atomic writes only.** The CLI handles this. Never edit `style.md` with shell redirection or non-atomic methods — a half-written file destroys the AE's accumulated work.
2. **Backup before reset.** `voice.py reset` makes `style.md.bak-<timestamp>` automatically. Tell the AE the backup exists when you reset.
3. **Don't interpret content.** The CLI never analyses what the AE pastes. It appends/replaces verbatim. Your job in chat is to **route** trigger phrases to the right subcommand, not to second-guess the AE's voice choices.
4. **Round-trip safety.** Every write is followed by a re-parse check inside `voice.py`. If parsing breaks after the edit, the write fails and the original file is preserved.
5. **Two confirmations for reset.** The AE must clearly say something destructive (e.g. "yes, reset", then "yes, I'm sure"). Only then call `reset --confirm-twice`.
6. **`clean up my voice` is interactive.** Read the file, propose changes inline in chat, get explicit AE approval, *then* write. Never silently rewrite their work.

## Companion skills

- `leads-hunt-outreach` — the consumer. Reads `style.md` fresh on every draft. Never writes it.
- `leads-hunt-setup` — bootstraps the workspace, including a blank `style.md` placed via this skill's `init` (or by setup itself).

## References

- `references/style-schema.md` — canonical contract for `style.md`. Read this if the AE asks "what's in my voice file" abstractly.
- `references/empty-skeleton.md` — the blank template written by `init` and `reset`.
- `references/iteration-tips.md` — guidance for the AE on how to teach voice over time. Quote from this when they ask "how do I make this better".
