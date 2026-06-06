# Lead philosophy: aggregators only — no consumers, no model builders

> **Sell to companies whose *product* uses AI by integrating third-party APIs. Skip companies that use AI internally for ops, AND skip companies that built their own proprietary model.**

This is ClawHunt's foundational filter. It runs **before** any scoring — if a candidate fails this filter, skip immediately and don't burn cycles on the rubric.

## The three buckets

Every candidate falls into exactly one of these three buckets:

| Bucket | What they do | Will they buy BytePlus AI APIs? |
|---|---|---|
| **AI aggregator** ✅ ship | Build user-facing products by integrating third-party AI APIs (Stable Diffusion, GPT, Claude, Seedream, etc.) | **YES** — they're our buyer. Their user growth → more API calls → more BytePlus revenue. They benchmark vendors and switch on quality/price/latency. |
| **AI model builder** ❌ skip | Train, own, and operate a proprietary AI model that drives their product. Their company *is* AI infrastructure for their domain. | **NO** — they compete with us at the model layer. Their growth → more own-compute, not API spend. Selling them our model is selling them their competition. |
| **AI consumer** ❌ skip | Use AI internally for marketing/sales/ops. AI output never reaches their customer. | **NO** — they're not the buyer; their AI tool's vendor is. Their AI usage is bounded by employee headcount, not user growth. |

## The core distinction

**AI Producers** = good leads.
Companies whose own product, platform, or feature exposes AI capabilities to **end users / customers**. The customer interacts with AI output.

Examples:
- Image generators (Dreamwave AI for headshots, BLNG AI for luxury fashion concepts)
- Video creation tools (StoReel, Choppity, OpusClip)
- E-commerce 3D viewers / configurators (Emersya, Zakeke, Aryel)
- AR shopping platforms (London Dynamics, Modelry)
- AI design tools (DreamzAR, Decor8 AI, Rawshot)
- Indie game studios building AI-asset pipelines (Bitmagic, Series Entertainment)

These companies have:
- Technical buyers (CTO / VP Eng / ML lead)
- AI infrastructure budget that scales with their MRR
- A practice of benchmarking model vendors
- Switching cost lower than expected (they already have abstraction layers)
- Volume that grows linearly with their own customer growth

**AI Consumers** = bad leads (skip).
Companies that use AI internally for their own operations. Only their **employees** see AI output.

Examples:
- A retailer whose marketing team uses ChatGPT for ad copy
- A bank whose support team uses an AI assist tool
- A consulting firm whose analysts use copilots for research
- A SaaS company whose CS team uses an AI ticket triager
- An e-commerce brand whose design team uses Midjourney internally

These companies are **not our buyer**. Their AI vendor's vendor (the foundation-model provider behind the SaaS tool they pay for) is. Volume is fixed (seat licenses), not API-call-driven.

## The model-builder check (added 2026-05-05 after FurniMesh)

After confirming a candidate is a producer (Filter 0a passes), you MUST also confirm they're an **aggregator**, not a **model builder**. This is Filter 0b.

**Model builder signals (these all → SKIP):**

- Research papers, arxiv links, academic publications listed on the site
- Phrases like "our proprietary model", "trained on X dataset", "we built", "research-backed"
- Funding from research grants (NSF, NextGenerationEU, DARPA, Horizon Europe, NIH)
- ML / research team prominently featured (with PhD signal)
- Pricing model based on training tier or compute (e.g., "$X per 1K training tokens")
- They sell an API to *other* businesses (they're a model provider, not a model consumer)
- Open-source releases of their model architecture / weights
- Self-description as "infrastructure", "platform", "foundation", or "model"

**Aggregator signals (these all → KEEP, proceed to scoring):**

- "Powered by [SomeAI]", "Built on [FoundationModel]"
- Integrations / tech-stack page lists third-party AI services (OpenAI, Anthropic, Stable Diffusion, BytePlus, etc.)
- Application-layer focus: UI/UX, workflow automation, vertical-specific business logic
- Per-output / per-credit pricing (passing through API costs, with margin)
- Language like "use any model", "switch providers", "we orchestrate", "we integrate"
- Fast product iteration cadence (suggests not bottlenecked by model training cycles)
- Their own focus is the *application*, not the *model*

**Canonical anti-example: FurniMesh** (shipped 2026-05-05, retroactively flagged as wrong fit)
- "Image-to-3D for furniture with parts separation" — their core IP is a furniture-specific image-to-3D model
- "Research-backed" — academic origin
- NextGenerationEU-funded — research-grant-funded model R&D
- They are infrastructure for furniture 3D, not a customer of furniture 3D infrastructure
- Selling them Seed3D 2.0 means selling them their competitor

When a candidate's website shows a mix of signals (e.g., uses third-party APIs but ALSO mentions a custom model), default to **skip** unless the custom model is clearly a fine-tune wrapper rather than a from-scratch trained model.

## Litmus tests (apply when ambiguous)

**Litmus 1 — Producer vs Consumer:** Does the lead's customer see AI output, or only their employees?

- **Customer sees AI output** → producer → check Litmus 2.
- **Only employees see AI output** → consumer → skip.

**Litmus 2 — Aggregator vs Model builder (NEW):** When you load their site, do you see "powered by / integrated with" language, OR do you see "our model / we trained / proprietary architecture" language?

- **Powered-by / integrated** → aggregator → ship.
- **Our model / we trained / proprietary** → model builder → skip.
- **Both, mixed** → default to skip; ambiguity wastes BD's time.

Edge cases resolved by these tests:
- A SaaS with an "AI assistant" feature, white-labeling Claude or GPT → **aggregator producer** → ship.
- A SaaS with an "AI assistant" using their own foundation model → **model builder** → skip.
- An agency delivering AI-generated work via OpenAI subscription → **aggregator producer** → ship.
- An agency using AI internally to speed up traditional creative work delivered as static files → **consumer** → skip.
- A research lab that just spun out a startup with one paper → **model builder** (likely) → skip.
- A vertical 3D platform that uses Tripo / Meshy under the hood → **aggregator producer** → ship.

## Why this matters for BytePlus specifically

BytePlus sells **infrastructure** — Seedream, Seedance, Seed3D, Seed (VLM) APIs that get called per-image, per-video, per-3D-asset. A producer's API call volume scales with their own user growth. A consumer's API call volume is bounded by their headcount.

Producers compound. Consumers cap.

## How to score producers (after Filter 0 passes)

Once Filter 0 passes (= confirmed AI producer), proceed to the regular scoring rubric. Producer status is a precondition, not a scoring input — every candidate that reaches the rubric should already be a producer.

If you can't tell within 2 minutes of research whether they're a producer or consumer, default to **skip**. Ambiguous cases waste BD's time downstream.

## How to source producers

When picking discovery angles for the day's hunt, bias toward sources that surface AI producers:

- ProductHunt AI launches (creators are by definition shipping AI to end users)
- YC / Antler / a16z speedrun batches (early-stage AI-native)
- Clutch / DesignRush listings tagged "AI services" (agencies productizing AI)
- Shopify / TikTok Shop AI app stores (3rd-party developers)
- itch.io / Steam Direct indie pages (game devs shipping AI features)
- "AI X for Y" search patterns ("AI try-on for fashion", "AI 3D for furniture")

Avoid sources that surface AI consumers:
- "Top X companies adopting AI in 2026" listicles (these are consumers)
- Enterprise digital-transformation case studies
- "How {Big Brand} uses AI internally" coverage
