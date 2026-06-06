# BytePlus AIGC Products: Outreach Cheatsheet

Quick reference for crafting outreach angles. Pull product specs from `shared/kb/entities/` for full detail.

## Seedream 4.5 — Image generation

- **Modes**: text-to-image, image editing, image-to-image
- **Strengths**: photorealism, product photography, style consistency
- **API endpoint**: `https://ark.ap-southeast.bytepluses.com/api/v3/images/generations`
- **Customer pitch**: "high-quality image gen API with low Asia latency"
- **Reference users**: e-commerce platforms, marketing creative tools, design agencies

## Seedance 2.0 — Video generation

- **Modes**: text-to-video, image-to-video, image-to-video first+last frame
- **Strengths**: synced audio (`generate_audio: true`), motion realism, 4-15s clips
- **Resolutions**: 480p / 720p / 1080p
- **Aspect ratios**: 16:9 / 9:16 / 1:1 / 21:9 / adaptive
- **API endpoint**: `https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks`
- **Customer pitch**: "i2v + t2v with native audio, Asia low-latency"
- **Reference users**: microdrama platforms, sports highlights, social video tools

## Seed3D 2.0 — 3D asset generation

- **Modes**: text-to-3D, image-to-3D
- **Strengths**: mesh + textures, fast iteration
- **Customer pitch**: "API for generating 3D assets at scale"
- **Reference users**: game devs, e-commerce 3D viewers, AR shopping

## Hyper3D Gen2 — High-fidelity 3D

- **Strengths**: cinematic quality, AAA-tier rendering
- **Customer pitch**: "high-fidelity 3D for premium use cases"

## HiTem3D 2.0 — Item-specialized 3D

- **Strengths**: object / item-focused 3D (catalog, e-commerce)
- **Customer pitch**: "specialized 3D for product catalogs"

## Common API region

- **SEA (Asia/Pacific)**: `ark.ap-southeast.bytepluses.com` — best for non-China traffic
- **CN (Volcengine)**: `ark.cn-beijing.volces.com` — for mainland China deployments
- **i18n**: `ark-i18n-tt.tiktok-row.net` — TikTok integrations

## Competitor pricing context (for positioning)

| Competitor | Their pricing | BytePlus advantage |
|---|---|---|
| Runway Gen-3 | $0.05/sec ($3/min) | Lower at volume |
| Pika 1.5 | $35/mo unlimited (low cap) | Higher cap, API-first |
| Luma Dream Machine | $0.4 per 5s (high) | Cheaper |
| Tripo (3D) | $0.05/asset | Comparable, faster |
| Meshy | $0.10/asset | Cheaper at volume |

(Update quarterly; competitors change pricing.)

## Common objections + responses

- **"We use OpenAI / Anthropic for everything"** → "Those don't do video/image gen. BytePlus is the AIGC layer, complementary not competitive."
- **"We're using Runway/Pika"** → "Have you compared cost at your volume? At >100 video gens/day, BytePlus is cheaper."
- **"Latency"** → "Asia gateway means <500ms latency for SEA users."
- **"Quality"** → "Free trial credits, 50 video generations to compare."

## Source docs

For deep technical questions, point at:
- API doc EN: https://docs.byteplus.com/en/docs/ModelArk
- Pricing: https://docs.byteplus.com/en/docs/ModelArk/pricing
- BytePlus customer cases: https://www.byteplus.com/en/customer-stories

## Seed 2.0 LLM pricing — SA budget sizing

When prospects ask "what can $X/month buy me on Seed 2.0?", use these official BytePlus ModelArk numbers (≤128K prompt tier; doubles above 128K). Confirmed against `docs.byteplus.com/en/docs/ModelArk/1544106` (2026-05).

| Tier | Input $/M | Cache-hit $/M | Output $/M | Cache discount |
|---|---|---|---|---|
| Mini | $0.10 | $0.02 | $0.40 | 5× |
| Lite | $0.25 | $0.05 | $2.00 | 5× |
| Pro  | $0.50 | $0.10 | $3.00 | 5× |

Cache *storage* is $0.0083/M-token-hour — negligible (1M cached for 24h ≈ $0.20/day).

**3rd-party quotes you'll see online ($0.47/$2.37 for Pro etc.) are stale or non-BytePlus resellers — quote the docs.byteplus.com numbers.**

### Budget → daily token capacity

For $1,200/month ($40/day) per model, common workload shapes:

| Workload (in:out) | Mini/day | Lite/day | Pro/day |
|---|---|---|---|
| 1:1 chat (no cache) | ~160M | ~35.5M | ~22.8M |
| 1:4 agent/RAG (no cache) | ~148M | ~28.6M | ~18.4M |
| 1:1 chat (100% cached input) | ~190M | ~39M | ~25.8M |
| 1:4 agent (100% cached input) | ~123M | ~24.7M | ~16.5M |

**Key insight for prospects:** caching benefit shrinks when output dominates the bill. A 1:4 in:out workload with 100% input caching saves only ~10-15% vs no cache, because output is 80% of the cost. Caching wins big on 1:1 (chat memory, system-prompt reuse) and 4:1 (RAG, classification, extraction).

**Math template** (cost per "unit" of 1 in-token + R out-tokens):
```
cost_per_M_units = input_price + R * output_price
daily_units = $40 / cost_per_M_units
daily_tokens = daily_units * (1 + R)
```
