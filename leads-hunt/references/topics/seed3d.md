---
slug: seed3d
display_name: Seed3D 2.0
enabled: false
---

# Topic: seed3d (Seed3D 2.0)

3D asset generation. Distinct ICP from `aigc-visual` because the buyer profile is different (game devs and 3D commerce platforms, not marketing tools).

## BytePlus product fit

- **Seed3D 2.0** ([entity ref](../../../../shared/kb/entities/seed3d-2-0.md)) — text-to-3D, image-to-3D, mesh + textures.
- **Hyper3D Gen2** ([entity ref](../../../../shared/kb/entities/hyper3d-gen2.md)) — high-fidelity rendered 3D.
- **HiTem3D 2.0** ([entity ref](../../../../shared/kb/entities/hitem3d-2-0.md)) — item / object specialized 3D gen.

For outreach, lead with Seed3D 2.0 (most general). Mention Hyper3D for high-fidelity use cases (cinematics, AAA-tier gaming).

## ICP

**All entries below must satisfy [Filter 0](../lead-philosophy.md): the company's own product/feature must expose 3D asset generation or 3D-rendered output to *end users / customers*, not just to internal employees.** A real-estate firm whose internal modelers use AI 3D tools is a consumer — skip. A real-estate platform whose homebuyers walk through AI-generated 3D rooms is a producer — pursue.

AI producers we want (in order of fit):

- **Indie game studios + 1-50 person dev shops** whose shipped game contains AI-generated 3D assets visible to players. NOT studios that use AI 3D tools internally for prototyping but ship hand-modeled assets.
- **AR/VR content tools** (Unity / Unreal plugin builders, AR shopping platforms, VR education) — their end users interact with AI-generated 3D content.
- **E-commerce 3D viewer platforms** (furniture, apparel, automotive, jewelry, home decor) — customers spin / inspect / try AI-generated 3D models on the merchant's site.
- **Digital twin / industrial visualization** platforms whose customers (architects, facility managers, buyers) interact with AI-generated 3D scenes. NOT factories using internal AI 3D tools for ops planning.
- **NFT / metaverse asset platforms** (cautious — many are dead) where users mint, trade, or display AI-generated 3D assets.

**NOT in ICP (auto-skip on Filter 0 or competitor list):**
- AAA game studios with internal 3D pipelines (Activision, EA, Ubisoft) — they're typically AI consumers (internal pipeline tooling), not producers.
- Construction / architecture firms using AI 3D tools internally for client decks — consumers, not producers.
- Pure 3D model labs (Tripo, Meshy, Luma Genie, Rodin, Common Sense Machines) — direct competitors (separate auto-skip).
- Consumer 3D camera apps without commerce or content-creation angle (no scaled API spend).
- **Vertical-specific 3D model builders (Filter 0b — added 2026-05-05)**: companies that built their *own* image-to-3D or text-to-3D model for a specific domain. They compete with us at the model layer; selling them Seed3D 2.0 sells them their competitor.
  - **Canonical anti-example**: **FurniMesh** (image-to-3D model for furniture with parts separation, NextGenerationEU research-grant funded, "research-backed"). Their core IP is the model itself.
  - Other examples to skip: any "AI 3D for {vertical}" company where the website emphasizes "proprietary model", research papers, or ML-team-as-co-founder.

**ICP target (after Filter 0a + 0b pass)**: aggregators / integrators in 3D — companies who build user-facing 3D experiences by *consuming* third-party 3D-gen APIs. They wire Seed3D / Tripo / Meshy / Luma into a vertical product and ship it to customers.

## Search angles (rotate by day-of-week)

### Day-type A (Mon, Sat) — ProductHunt
- "3D asset generator" recent launches
- "AI game dev tool" recent launches
- "AR shopping" launches
- Vertical sweep fallback: indie game dev tools, AR plugin builders, e-commerce 3D viewers, digital twin apps

### Day-type B (Tue, Sun) — Regional
- Asia: AR shopping platforms (Korea, Japan especially)
- LATAM: e-commerce 3D viewers
- MENA: real estate digital twin tools
- Eastern Europe: indie game studios

### Day-type C (Wed) — Game-dev studios
- itch.io / Steam Direct: small-team studios (1-10 employees)
- Game-dev Twitter / Discord communities discussing AI tools
- Unity Asset Store / Unreal Marketplace plugin authors

### Day-type D (Thu) — YC / accelerators
- YC current batch + F2025: gaming, 3D, AR/VR categories
- a16z Games portfolio (high-signal for game-tech startups)
- YC Hard Tech / Industrial categories (digital twin, manufacturing 3D)

### Day-type E (Fri) — Feature additions
- Shopify / BigCommerce 3D viewer apps adding AI generation
- AR/VR platforms (Niantic, etc.) ecosystem partners
- Industrial software companies announcing AI-powered 3D features

## Negative signals (auto-skip, score → 0)

1. **BytePlus mention**: Seed3D, BytePlus, ByteDance, VolcEngine, Doubao on website.
2. **Direct competitor**: Tripo, Meshy, Luma Genie (3D), Rodin, Common Sense Machines, Stability3D, CSM.
3. **Featured on "top AI 3D generators" lists**.
4. **AAA studio profile** (>500 employees, internal 3D pipeline, no API need).
5. **Crypto / NFT-only profile** (likely zombie, tokenomics page = skip).

## High-yield verticals (TBD — fresh topic, accumulate over time)

This topic is new. Saturation/yield data will accumulate in `feedback-seed3d.md`. Initial guesses to test:

- **Indie game devs on YC** (Cardboard pattern proven for video; should work for 3D too).
- **E-commerce 3D viewer platforms** in furniture/automotive verticals.
- **AR shopping startups** in Korea/Japan (high BD blind spot).
- **Digital twin tools** for real estate — emerging vertical.
- **Game asset marketplaces** (Sketchfab competitors, etc.).

## Saturated verticals (initial guess, refine in SKILL.md Discovery Patterns)

- AI-native 3D model generators (competitors, all known).
- Crypto / metaverse asset platforms (mostly dead, low conversion).
- AAA studio outreach (won't buy API, have internal teams).

## Outreach angle templates

**For game devs:**
> Noticed [their game / 3D feature]. Seed3D 2.0 does t2v and i2v with [their style needs]. Worth a 15-min look at the API?

**For e-commerce 3D viewers:**
> Saw [their product viewer]. Seed3D could automate 3D model generation for new SKUs. Volume pricing might fit [their catalog size].

**For digital twin / industrial:**
> Saw [their visualization product]. Hyper3D Gen2 has [parameter advantage] for high-fidelity rendering. Could integrate as their AI generation backend.

**Voice rules**: same as aigc-visual. No em-dash, no AI-tells, terse.