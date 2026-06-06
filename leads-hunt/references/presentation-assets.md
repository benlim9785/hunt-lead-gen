# Presentation Assets

Reusable visual + narrative material for explaining the lead-gen pipeline to internal audiences (sales, leadership, peer SAs).

## When to load this

User asks for any of:
- "Make a writeup/presentation/deck about the pipeline"
- "Explain the lead-gen system to [sales / leadership / new SA]"
- "Update the [Lark doc / HTML page] about how this works"
- Tomorrow / next-week internal presentation prep

NOT for: running the pipeline, debugging it, adding a target. Those are SKILL.md proper.

## Canonical artifacts (live)

### Lark doc — internal long-form
- **URL**: `https://bytedance.larkoffice.com/docx/EemJd2csSo93jGxnU5alpulfgzh`
- **Token**: `EemJd2csSo93jGxnU5alpulfgzh`
- **Audience**: BytePlus internal, generalized to "lead-gen teams" (not SA-specific)
- **Last revision shipped**: 35 (2026-05-21), 1385 words, 4 inline diagrams
- **Structure**: TL;DR → old way → new way → doctrine → architecture → moat → self-learning → takeaways
- **Update via**: `lark-cli docs +update --api-version v2 --command overwrite --doc EemJd2csSo93jGxnU5alpulfgzh --content @file.md` (overwrite wipes images, preserves token)
- **Image insertion**: `+media-insert --file path.png --selection-with-ellipsis "X...Y" --before --align center --doc <token>` — ellipsis CANNOT cross heading boundaries, use single-line text within same paragraph

### HTML presentation — sales-friendly
- **Source**: `/tmp/leadgen-presentation/index.html` (~31KB, dark-theme, sticky TOC)
- **Audience**: BytePlus salespeople (NOT engineers); every technical term glossed in plain English BEFORE it lands
- **Hosting**: ephemeral via `cloudflared` quick tunnel (see skill `cloudflared-quick-tunnel`)
- **Sections**: hero → 30-sec → old way → new way → who this finds (3 customer cards) → one question (Filter 0) → inside → moat → smarter → takeaways
- **Last URL shipped**: `https://realm-responsibility-aspects-volunteers.trycloudflare.com` (ephemeral; will rotate on next launch)

## Diagrams (regenerable)

All in `/tmp/leadgen-*.png`:

| File | Shows | Render script |
|---|---|---|
| `leadgen-arch.png` | Full 4-phase architecture | `/tmp/render_leadgen.py` |
| `leadgen-old-workflow.png` | Manual lead-hunting flow with time leaks | (subagent-built, HTML in `/tmp/leadgen-*.html`) |
| `leadgen-new-glance.png` | 4 phases A-D + ready-to-send output | (subagent-built) |
| `leadgen-filter0.png` | Filter 0 decision tree (producers vs consumers) | `/tmp/render_filter0.py` |
| `leadgen-day-compare.png` | Side-by-side day timeline: Today (~3.5hr selling) vs Pipeline (~7hr) | `/tmp/render_three.py` |
| `leadgen-bouncers.png` | 4-gate horizontal dedup funnel with per-gate reject % | `/tmp/render_three.py` |
| `leadgen-feedback-loop.png` | Circular 5-node self-learning loop, inner dashed fast-loop | `/tmp/render_three.py` |

**Visual register**: bg `#020617`, container `rgba(15,23,42,0.5)` border `#1e293b`, 40px grid pattern, JetBrains Mono, rounded 1rem. Accent palette: cyan `#22d3ee`, emerald `#34d399`, amber `#fbbf24`, rose `#fb7185`, violet `#a78bfa`. Match this exactly when adding new diagrams — the doctrine is "image speaks louder than words" so visual cohesion across the deliverable matters.

## Voice rules (Ben's writing)

**Rejected on 2026-05-21**: marketing-landing-page voice. Ben pushed back: *"feels like too marketing oriented, i want it to be simple and concise. use visual diagram if possible."* The earlier version of this file recommended "every section ends with a 'why this matters for you' callout" and "analogies generously" — both got cut. Keep this section as-is; do not regress.

### Target voice: engineer's whiteboard

- Terse. Fragments fine. Strong verbs. Short sentences.
- NO em-dashes anywhere. Hyphens only.
- NO marketing fluff: "leverage", "ensure", "robust", "comprehensive", "dive into", "streamline", "Honest answer:".
- NO copywriter framings: "while we sleep", "while you sleep", "unfair advantage", "magic", "it just works", "WHY THIS MATTERS FOR YOU", "30-second version", "imagine", "think of it as".
- NO per-section "why this matters" callouts. The diagram makes the point.
- NO sustained analogies (bouncer chain, intern army, coffee-maker timer). One-shot inline glosses are fine; analogy-driven explanations are not. Audience is internal sales colleagues, not prospects being sold to.
- DO gloss every technical acronym ONCE inline, briefly: cron = scheduled task, ICP = ideal-customer profile, COGS = cost of goods sold, XHR = browser network call, CRM = customer DB. No multi-sentence detours.
- Concept first, mechanism second.

### Target structure: diagram-first

Each section: **headline → diagram → 3-5 short bullets → next section.** The diagram does the explaining. Bullets are footnotes to the diagram, not paragraphs.

Cut rule: if a sentence isn't either (a) labeling something in the diagram or (b) saying something the diagram can't show, cut it. Most paragraphs become 1-2 line bullets. Apply ruthlessly.

### Hero / header

- NO full-viewport hero. NO scroll-cue chevron. NO CTA buttons.
- Compact ~120px page header: title + meta line (`Internal presentation. YYYY-MM-DD.`) + one factual sentence summarizing the system.
- Example: `Cron jobs find AI-producer leads, dedup against Salesforce, draft outreach. Output: 5-15 pre-qualified leads in chat by 9:30.`

### Section names — prefer literal/technical over copywriter

| Avoid | Use |
|---|---|
| "The 30-second version" | `TL;DR` (or delete) |
| "The old way" | `Today` |
| "The new way" | `Pipeline` |
| "Who this finds" | `Example targets` |
| "The one question" | `Filter 0` |
| "What's inside" | `Phases` |
| "The unfair advantage no SaaS tool can copy" | `Moat: Layer N` |
| "How it gets smarter" | `Self-learning` |
| "What you can steal" | `Takeaways` |

### Length targets (full pipeline presentation)

- HTML: ~20KB body
- Rendered word count: 600-1400 words
- 7+ diagrams (more than text blocks). When prose does work a diagram could do, build the diagram instead.

### Diagram conversions that worked

- "Here's how the day differs" → side-by-side day-timeline (rose vs emerald color contrast).
- "We dedup in 4 layers" → horizontal funnel `[100] → Gate 1 → [70] → Gate 2 → [52] → Gate 3 → [42] → Gate 4 → [5-15]` with reject % per gate.
- "It learns from your ratings" → circular 5-node feedback loop with inner dashed fast-loop.

## Scrub list (terms that must NOT appear)

For external/generalized writeups: ClawHunt, Clawdia, ClawMander, Hermes, hunt-profile, any `*.py` filename, aigc-visual (lowercase slug), seed3d (lowercase slug), Sonnet, BD-corp.

Allowed in customer-fit context: BytePlus, Seedance, Seedream, Seed3D (capitalized), Seed-2.0, ModelArk, Skylark, DeepSeek, Salesforce, Sales Navigator, crmStatus, IN_CRM, ChatGPT, Claude (as prospect-product examples).

## Success-story customer cards

Three textbook AI-producer examples cached at `/tmp/success-cases-research.md`:

- **MotionFly** — solo-founder prompt-to-video, pre-seed (~$160 MRR), Seedance fit
- **Vectary** — Slovak/US 3D+AR design platform, Series-stage (~$3.2M ARR), Seed3D fit
- **Socialbu** — bootstrapped Lahore SMB SaaS, 18k users, LLM/Seedream fit

**Caveat (mandatory)**: BytePlus model usage is `[unverified]` for all three. Frame as "shape of company we're hunting", NOT "BytePlus customers". User to confirm internally before any external/customer-facing version drops the pill.

## Sub-agent fan-out pattern (works well here)

For presentation rebuilds, parallelize:
1. Research subagent → fact-check + reference cards
2. Writing subagent → narrative HTML/markdown
3. Diagram subagent → renders PNGs from HTML/SVG via Playwright

Then Clawdia handles: file copies, hosting, vision-verify, ship to user. Done in ~5 minutes wall-clock instead of 30+ in-context.

## Pitfalls

- **Sub-agent HTML grid bug**: `grid-template-columns: 1fr 200px` with `<nav>` before `<main>` puts nav in the wide column, content in the 200px sliver. Always specify `grid-template-areas` and `grid-area:` on children. See `cloudflared-quick-tunnel` pitfalls.
- **Vision-verify before shipping HTML**: Playwright screenshot → `vision_analyze` catches layout breaks the subagent's `wc -c` checks miss.
- **Vision false-negatives on short diagrams**: when an image is shorter than ~half the screenshot viewport (e.g. a 260px-tall funnel diagram in a 900px viewport), `scrollIntoView({block:'center'})` still bleeds adjacent content into frame and `vision_analyze` will describe the NEIGHBOR diagram, reporting your target as "not present". Fix: use `scripts/vision_check_diagram.py` which measures the image's bounding box and (a) centers it and (b) warns when viewport is too tall, suggesting a tighter viewport height. Saves several wasted vision calls per check.
- **Lark doc image-insert ellipsis**: cannot span heading boundaries. Use single-line selection within same paragraph.
- **Don't bloat SKILL.md with presentation prose**: that's why this file exists. SKILL.md governs running the pipeline; this file governs talking about it.
- **Don't regress the voice rules**: see "Voice rules" section. Marketing-landing-page voice was tried 2026-05-21 and explicitly rejected. New session that proposes "let's add a 'why this matters' callout" or "let's lead with a tagline hero" is wrong.
