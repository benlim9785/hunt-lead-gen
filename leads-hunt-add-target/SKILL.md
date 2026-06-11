---
name: leads-hunt-add-target
description: "Interactive scaffolding for new lead-gen topics. Creates a topic .md file under leads-hunt's references/topics/ via Lark chat."
author: Ben Lim
license: MIT
---

# leads-hunt-add-target

Conversational scaffolding for adding (or editing) a leads-hunt lead-gen topic. Encodes the right questions to ask so a new topic lands with a complete ICP doctrine on day one — not a half-defined slug that the daily agent then drifts on.

## When to use

User says any of:
- "add a leads-hunt target"
- "new lead-gen topic"
- "create a target for [X]"
- "add a hunting topic for [vertical]"
- "edit the [slug] target"

If the user just dumps a topic idea casually ("we should hunt for tabletop RPG art tools"), confirm whether they want to formally add it as a target before launching the Q&A — sometimes they're just thinking out loud.

## The pattern (do not skip steps)

1. **Q&A** — ask 8 structured questions, one batch at a time
2. **Draft** — synthesize answers into the topic markdown
3. **Review** — show the draft, ask for tweaks
4. **Write** — once approved, write to the leads-hunt skill's `references/topics/<slug>.md`
5. **Verify** — run `topic_registry.py` + curl `/api/targets`, confirm the new target appears
6. **Report** — short summary, link to the dashboard Targets page

Do **not** write the file before review. Topics define agent behavior for weeks; one review round is cheap insurance against fuzzy ICP encoding.

## Path resolution — where does the topic file land?

This skill writes into the **sibling** `leads-hunt` skill's `references/topics/` directory. The two skills are always installed together (as a pack), so they live as siblings in the same skills root — whether that's a workspace `skills/` dir or `~/.openclaw/skills/`.

Resolve the path like this at write time:

```python
import os, sys

# This skill's own directory (where SKILL.md lives) is known to the agent at runtime.
# When the agent executes this skill, it has the SKILL.md path; derive the skill dir from it.
THIS_SKILL_DIR = os.path.dirname(os.path.abspath(SKILL_MD_PATH))   # .../leads-hunt-add-target
SKILLS_ROOT    = os.path.dirname(THIS_SKILL_DIR)                    # .../skills (or pack root)
LEAD_GEN_DIR   = os.path.join(SKILLS_ROOT, 'leads-hunt')
TOPICS_DIR     = os.path.join(LEAD_GEN_DIR, 'references', 'topics')

# Sanity check — fall back to a CLI / arg override if discovery fails:
if not os.path.isdir(LEAD_GEN_DIR):
    # Allow caller to pass --lead-gen-skill <abs path> to override.
    override = os.environ.get('LEADS_HUNT_SKILL_DIR')
    if override and os.path.isdir(override):
        LEAD_GEN_DIR = override
        TOPICS_DIR = os.path.join(LEAD_GEN_DIR, 'references', 'topics')
    else:
        sys.exit(
            f"Could not locate sibling 'leads-hunt' skill at {LEAD_GEN_DIR}. "
            f"Set LEADS_HUNT_SKILL_DIR=/path/to/leads-hunt or pass --lead-gen-skill."
        )

os.makedirs(TOPICS_DIR, exist_ok=True)
```

This works for both `openclaw skills install ./leads-hunt-pack/leads-hunt-add-target` (workspace) and `openclaw skills install --global ./leads-hunt-pack/leads-hunt-add-target` (`~/.openclaw/skills/`) because the two skills always end up siblings under the same root.

## Step 1 — Q&A

Ask these in **two batches** (4+4). Asking all 8 at once overwhelms; one-at-a-time is too slow. Two batches is the sweet spot.

### Batch 1 — Identity & product fit

Present as a numbered list:

```
Tell me about the new target:

1. **Slug** — short, lowercase, hyphens only (e.g. `manga-tools`, `tabletop-art`). This becomes the filename and URL slug.
2. **Display name** — human-friendly (e.g. "Manga & Webtoon Tools").
3. **Product fit** — which of your products does this target? (Image gen / video gen / 3D gen / other — depending on the AE's leads-hunt setup.) One sentence on which fits best for this vertical.
4. **One-liner pitch** — what is this target in plain English? "Bootstrapped tabletop-RPG art generators that need high per-session image volume but live on r/DnD not ProductHunt."
```

After the user answers, validate:
- **Slug uniqueness**: check that `<TOPICS_DIR>/<slug>.md` doesn't exist (use the resolved `TOPICS_DIR` from the path-resolution snippet above). If it does, ask if they want to edit the existing one or pick a different slug.
- **Slug format**: lowercase, hyphens, no spaces, no underscores. Suggest a fix if malformed.
- **Product fit clarity**: if the answer is "all of them", push back — usually the target leans heavily toward one. Vague product fit → vague outreach.

### Batch 2 — ICP doctrine

```
Now the ICP details:

5. **ICP — who's a good lead?** List 3-5 specific company archetypes you want to find. Be concrete: "Shopify apps for fashion try-on with paying merchants" beats "fashion AI companies."

6. **ICP — who's auto-skip?** Beyond the global skip rules (own-product mention, direct competitors, AI-name branding, well-known platforms), are there target-specific skip rules? E.g. for `manga-tools`: skip companies with their own trained illustration model.

7. **Where do you find these?** Pick a discovery method bias — does this vertical live on ProductHunt, Shopify App Store, YC batches, regional press, niche subreddits, trade pubs? Free-form, list 3-5 sources.

8. **Outreach voice** — any voice/tone notes specific to this vertical that differ from the AE's default (no em-dash, terse, light emoji)? E.g. "more technical for dev tools", "warmer for indie creators."
```

After Batch 2, ask the **overrides question** only if the user has said anything suggesting non-standard config:

```
Optional — any per-target overrides?

- **`ceiling`** (default 5) — max leads per day for this target. Lower if exploratory, higher if proven.
- **`score_floor`** (default 8) — min score to ship. Lower (7) if calibrating, higher (9) if mature.
- **`candidate_target`** (default 18) — how many candidates the agent tries to research per run.

Reply "use defaults" or specify only the ones you want to override.
```

If the user said nothing suggesting non-standard config and the target sounds normal, **skip this question entirely** — defaults are correct ~90% of the time and asking creates decision fatigue.

## Step 2 — Draft synthesis

Map the answers to the topic file template:

```markdown
---
slug: <slug>
display_name: <Display Name>
enabled: true
# Optional overrides (omit to inherit from config.json):
# ceiling: 5
# score_floor: 8
# candidate_target: 18
---

# Topic: <slug> (<Display Name>)

<one-liner pitch — answer to Q4>

## Product fit

<answer to Q3, expanded into 1 paragraph + bullet list of products with links to entity refs if known>

## ICP (Ideal Customer Profile)

**All entries below must satisfy [Filter 0](../lead-philosophy.md): the company's own product/feature must expose AI [image|video|3D] output to *end users*, not just to internal employees.**

AI producers we want (in order of fit):

<answer to Q5 — bullet list, 3-5 archetypes, concrete>

**NOT in ICP (auto-skip on Filter 0):**
- Pure AI [image|video|3D] model labs (competitors — separate auto-skip)
- Companies using AI internally for marketing/sales/ops (consumers)
<answer to Q6 — target-specific skip rules>

## Search angles

<answer to Q7 — 3-5 sources, organized by day-type if natural, otherwise as a flat list>

If the user gave fewer than 5 sources or didn't think in terms of day-types, don't force-fit a multi-day-type structure — it's overkill for a new target. Use a flat list. Day-type rotation can be added later once the target has run for a few weeks and the user knows which sources work.

## Negative signals (auto-skip, score → 0)

Any of these = SKIP and append to skip-list:

1. **Own-product mention on website**: any of the AE's product/brand names anywhere in the site, blog, or product docs.
2. **Direct competitor**: <list direct competitors for this vertical>
3. **Featured on "top AI [vertical] tools" lists** with prominent placement.
<plus any custom rules from Q6>

## Outreach angle template

<draft a 1-2 sentence template based on Q3 + Q4 + Q8 voice notes>

**Voice rules** (always):
- No em-dash (—) or en-dash (–). Use period, comma, or parenthesis.
- Lowercase opener fine ("hi @X").
- No "Hope this helps", no "Let me know if you have any questions", no "In summary".
<plus any voice notes from Q8>
```

**Don't pad the draft.** If the user gave thin answers, the draft should be thin — better to ship a focused 60-line target than a bloated 150-line one with filler. The Discovery Patterns Learned section in the `leads-hunt` skill's SKILL.md is where breadth lives; per-target files are doctrine, not encyclopedia.

## Step 3 — Review

Show the full draft as a markdown code block. Ask:

```
Draft above. Anything to tweak before I write it to references/topics/<slug>.md?

- "ship it" → I write the file
- "change X to Y" → I revise and re-show
- "add a [section]" → I expand
```

Common tweaks at this stage:
- ICP archetypes are too broad → user names a specific competitor to anchor it
- Voice template doesn't sound like the user → swap a few words
- Missed a competitor in negative signals → add it

Cap at 2 review cycles. If we hit a 3rd cycle, the target is under-defined — pause and suggest the user pilot-run it manually for a week before formalizing.

## Step 4 — Write

Resolve `TOPICS_DIR` per the **Path resolution** section at the top, then write directly:

```python
target_path = os.path.join(TOPICS_DIR, f"{slug}.md")
with open(target_path, 'w', encoding='utf-8') as f:
    f.write(draft_content)
print(f"wrote {target_path}")
```

No `hermes -z`, no profile shell-out — this is a plain Python file write into the sibling skill's directory.

## Step 5 — Verify

Three checks, all must pass. Resolve `LEAD_GEN_DIR` first (per the path-resolution snippet).

```bash
# (a) Registry parses the new file
cd "$LEAD_GEN_DIR/scripts"
python3 topic_registry.py | python3 -c "
import json,sys
d=json.load(sys.stdin)
slugs=[t['slug'] for t in d['topics']]
print('registry slugs:', slugs)
assert '<new_slug>' in slugs, f'{<new_slug>} missing from registry'
print('OK')
"

# (b) Dashboard /api/targets shows the new target
curl -sf http://127.0.0.1:3838/api/targets \
  -H 'Authorization: Bearer <token-from-AE-config>' \
  | jq '.targets | map(.slug)'
# Expect: list contains <new_slug>

# (c) Filename matches slug field (catches typos)
grep -E "^slug: " "$LEAD_GEN_DIR/references/topics/<new_slug>.md"
# Output must say "slug: <new_slug>" exactly
```

If any check fails:
- Registry parse fail → frontmatter is malformed (most likely a stray colon or unquoted special char in display_name). Read the file, find the bad line, ask user.
- /api/targets missing → the dashboard caches nothing, but if it doesn't appear, the file path is wrong. Verify with `ls "$LEAD_GEN_DIR/references/topics/"`.
- Slug/filename mismatch → fix the frontmatter slug field to match the filename (or rename the file). The registry drops mismatched files with a warn.

## Step 6 — Report

Short summary, no fluff:

```
Added target: <display_name> (<slug>)
- Path: <leads-hunt skill>/references/topics/<slug>.md
- Dashboard: https://<your-tunnel-host>/targets
- Tomorrow's scheduled discover-all run will include it.
```

If the AE wants the discover-all timing to change, that's an AIME-native scheduler update against the leads-hunt recurring tasks — not something this skill touches.

```
Want to set per-target overrides (ceiling/score_floor/candidate_target) or leave as defaults?
```

The post-write overrides offer is a second chance to tune — sometimes users see the rendered card on the dashboard and realize they want a tighter ceiling for the first month.

## Pitfalls

1. **Don't auto-enable a thin target.** If the user gave one-word answers and you're padding the draft, set `enabled: false` in the frontmatter and tell them: "Marked as disabled. Flip to `true` after you've thought through the ICP a bit more." Better to ship a paused target than a rushed one that pollutes the daily agent.

2. **Don't invent competitors / verticals.** If the user doesn't name specific competitors for the negative-signals list, leave that bullet generic ("Direct competitor: skip companies that already build their own [output type] generation model"). Inventing names that aren't actually competitors creates false skip rules.

3. **Slug regex**: `^[a-z0-9][a-z0-9-]*[a-z0-9]$`. Reject anything else with a fix suggestion: `manga_tools` → `manga-tools`, `Manga Tools` → `manga-tools`, `mangatools_2` → `mangatools-2`.

4. **Edit mode** (slug already exists): load the existing file as the starting draft, ask "what's changing?" instead of running the full Q&A. Most edits are scope refinements, not full rewrites.

5. **The `enabled: false` override**: if the user explicitly says "draft this but don't run it yet", set `enabled: false`. This pre-stages a target for review before activation. The `/targets` page shows it as "Disabled" so you don't forget.

6. **Don't run discover/dedup commands.** This skill scaffolds the target file. It does not trigger a discovery run. The next scheduled cron picks it up automatically. If the user wants an immediate run, that's a separate explicit request — and it lives in the `leads-hunt` skill, not here.

7. **Path is resolved, not hardcoded.** Use the path-resolution snippet to find the sibling `leads-hunt` skill. Do not hardcode `/root/...` paths — this skill is meant to ship to multiple AEs whose installs may live in `./skills/` or `~/.openclaw/skills/`. The `LEADS_HUNT_SKILL_DIR` env override is the escape hatch for unusual layouts.

## Verification example (from a real run)

User said "add a target for tabletop RPG art tools." Resulting file should look roughly like:

```markdown
---
slug: tabletop-art
display_name: Tabletop RPG Art Tools
enabled: true
---

# Topic: tabletop-art (Tabletop RPG Art Tools)

Bootstrapped AI art tools serving D&D/Pathfinder/TTRPG players — high per-session
image volume (20+ portraits per campaign), zero coverage from incumbents in the
AE's product line. Lives on r/DnD, ENWorld forums, and Kickstarter, not ProductHunt.

## Product fit

Primarily image generation (character portraits, scene art, item illustrations).
Some video opportunity for VTT (virtual tabletop) animated tokens.

...
```

That's the target shape: tight, opinionated, names the vertical's actual home (Reddit/ENWorld), sets up the scoring agent with concrete ICP anchors.
