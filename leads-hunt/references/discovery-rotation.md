# Discovery Method Rotation

Pick discovery method by **today's day-of-week** (MYT). Both topics use the same rotation; the topic-specific search angles narrow the focus.

## Source bias — pick producer-rich channels

Per [`lead-philosophy.md`](./lead-philosophy.md), every candidate must pass Filter 0 (AI producer, not AI consumer). Some sources are dense with producers; others are dense with consumers. Bias every day-type's hunt toward producer-rich sources and avoid the consumer-heavy ones.

**Producer-rich (preferred):**
- ProductHunt AI launches (creators are by definition shipping AI to end users)
- YC / Antler / a16z speedrun / 500 Global batches (early-stage AI-native)
- Clutch / DesignRush "AI services" agency listings (they productize AI for clients)
- Shopify / TikTok Shop AI app stores (3rd-party developers exposing AI features)
- itch.io / Steam Direct indie game pages (devs shipping AI features in games)
- "AI {X} for {Y}" search patterns ("AI try-on for fashion", "AI 3D for furniture")
- Unity Asset Store / Unreal Marketplace AI plugin authors

**Consumer-heavy (avoid as primary discovery; they generate weak candidates):**
- "Top X enterprises adopting AI in 2026" listicles
- McKinsey / Gartner "AI in {industry}" reports
- "How {Big Brand} uses AI internally" coverage
- Digital-transformation case studies from systems-integrator partners
- LinkedIn posts from execs at non-AI companies announcing they "are exploring AI"

When a candidate appears in a producer-rich source but on inspection turns out to be a consumer (e.g., a Clutch agency that uses AI internally but doesn't ship AI deliverables), apply Filter 0 and skip — don't try to justify keeping them.

## Day-type table

| Day | Day-type | Method |
|---|---|---|
| Mon | A | ProductHunt & launches |
| Tue | B | Regional discovery |
| Wed | C | Agencies & services |
| Thu | D | YC / accelerator hunting |
| Fri | E | SaaS feature additions |
| Sat | A | ProductHunt (alt: vertical sweep if PH blocked) |
| Sun | B | Regional discovery |

## Day-type A — ProductHunt & launches

- Browse ProductHunt for recent AI creative tool launches (<1k upvotes for niche signal)
- Check ProductHunt collections: AI tools, marketing, video, 3D
- Hunt indie launches with active "Made on PH" badges

**Saturday fallback** (PH often Cloudflare-blocked on weekends):
- "vertical sweep" — pick 4-5 niches and hunt within each (microdrama, eLearning, fashion AI, sports video, webtoon for `aigc-visual`; indie game dev, AR/VR plugin, e-commerce 3D for `seed3d`)
- Validated 2026-04-25, see Discovery Patterns Learned in SKILL.md

## Day-type B — Regional discovery

- LATAM: Brazilian / Mexican / Argentine creative-tech startups
- MENA: UAE, Saudi marketing tech (be careful, often already in BD pipeline)
- Eastern Europe: Polish / Czech / Estonian SaaS adding AI
- India: niche players, NOT well-known AI platforms
- Indonesia / Vietnam / Thailand creator-economy (low priority but occasional gem)

## Day-type C — Agencies & services

- Clutch.co agencies advertising AI services (filter: <50 employees)
- DesignRush agency listings mentioning generative AI
- Local agency directories in target regions
- Media production houses automating with AI

## Day-type D — YC / accelerator hunting

- YC current batch (`ycombinator.com/companies?batch=W26&...`)
- YC F2025 (still active)
- Techstars cohorts
- 500 Global Creators Ventures (validated as high-yield 2026-04-02)
- Antler London + Antler Asia
- a16z Games portfolio (for `seed3d`)
- Harvard Innovation Labs (validated 2026-04-24)

## Day-type E — SaaS feature additions

- TechCrunch articles "X adds AI features"
- ProductHunt "adds AI" tagged launches
- Vertical-specific: real estate AI, fashion AI, e-learning publishers
- Established SaaS companies with recent AI-powered feature announcements

## Rules

1. **Use TODAY's day-type, not yesterday's.** Even if yesterday's method had high yield, vary discovery to avoid burning the same source.
2. **Track method per lead** in the `DiscoveredVia` CSV column.
3. **If method yields fewer than 10 candidates** after 30 minutes, pivot to a different vertical or fall back to vertical sweep.
4. **Read `feedback-<topic>.md`** before discovery to learn from prior runs (saturated verticals, high-yield ones).

## Cumulative method-yield tracking

Phase D's Method effectiveness is captured in SKILL.md (Discovery Patterns Learned). Update the skill via skill_manage when a method falls off or a new one proves out.
