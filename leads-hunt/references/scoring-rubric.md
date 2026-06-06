# Scoring Rubric (1-10)

## Filter 0: aggregator-only check (precondition, two parts)

> **Sell to companies whose *product* uses AI by integrating third-party APIs. Skip consumers AND model builders.**

Before scoring, confirm the candidate passes BOTH parts of Filter 0:

**Filter 0a — AI producer (not consumer)**: Does the lead's customer see AI output, or only their employees? Customer-facing AI → producer (continue). Employee-facing AI only → consumer (skip).

**Filter 0b — AI aggregator (not model builder, added 2026-05-05)**: Does the company integrate third-party AI APIs into their product, or did they train and own a proprietary model? Aggregator (uses APIs) → ship-eligible (continue to scoring). Model builder (owns the model) → skip — they're a competitor at the model layer, not a customer.

Quick model-builder signals to check: "proprietary model", "trained on X", research-grant funding (NSF / NextGenerationEU / DARPA / Horizon), arxiv/research papers prominently linked, ML/research team prominently featured, open-source model weights, sells an API to other businesses.

If ambiguous after 2 minutes of research on either filter, default to skip. Full doctrine: [`lead-philosophy.md`](./lead-philosophy.md).

**Canonical anti-example (model builder we wrongly shipped 2026-05-05): FurniMesh** — built their own image-to-3D model for furniture, NextGenerationEU-funded, "research-backed". They are infrastructure for their domain, not a customer of infrastructure.

---

## Scoring (1-10)

Once Filter 0 passes, score each candidate 1-10 weighted toward "unlikely to be in CRM" and "high-volume API potential". **Only ship score ≥8.** Below that, skip and log reason.

## Score bands

| Score | Profile |
|---|---|
| **9-10** | Small/new company, no BytePlus mention, clear product fit, regional/niche, NOT on any "top AI tools" list, named contact reachable |
| **8** | Solid fit, no BytePlus mention, named contact discoverable |
| **7** | Decent fit but slightly visible (medium funding round, some social presence) — usually filtered out |
| **5-6** | Larger/visible company, might already be contacted by BD; needs strong reason to ship |
| **1-4** | Well-known AI platform — SKIP ENTIRELY, add to skip-list |

## Scoring inputs

Each input adjusts the base score:

| Input | Adjustment |
|---|---|
| Company has BytePlus/Seedream/Seedance mention on site | -10 (auto-skip) |
| Company is on any "top AI X tools" listicle | -3 (likely already contacted) |
| Company has >50K social followers + AI-prefixed branding | -3 |
| Company has named contact (founder LinkedIn or contact email) | +1 |
| Company size 1-50 (target ICP for this skill) | +1 |
| Company has clear vertical fit (matches topic ICP exactly) | +1 |
| Company is funded ≤$5M total | +1 (genuine API customer profile) |
| Company is bootstrapped + revenue-generating | +1 |
| Company is in a saturated vertical (per SKILL.md Discovery Patterns) | -2 |
| Company is in a high-yield vertical (per SKILL.md Discovery Patterns) | +1 |

## Hard skips (force score 0, do NOT ship)

- **Self-disclosed BytePlus customer/partner**: any mention of Seedream, Seedance, ByteDance, VolcEngine, Doubao, Jimeng on website, LinkedIn About, or product docs.
- **Direct AIGC competitor**: company sells the same product (AI image gen, AI video gen, AI 3D gen). E.g., Runway, HeyGen, Synthesia, D-ID, Pika, Tripo, Meshy.
- **Featured on "top AI tools" lists** with prominent placement.
- **Listed in BytePlus public case studies / customer logos**.

## Final ship rule

```
if score >= 8 AND not in_crm AND not auto_skip:
    ship to CSV
else:
    skip and note in run-log
```

## Why score ≥8 (not ≥7)

Old TASK.md used score ≥7. With Sales Nav dedup catching CRM hits, we can afford to be pickier on quality. Empirically: score-7 leads sometimes had thin fit; score-8+ leads had clear product alignment. Easier for Ben to read 5 strong leads than 5 marginal ones.
