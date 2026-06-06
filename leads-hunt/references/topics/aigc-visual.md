---
slug: aigc-visual
display_name: Seedream + Seedance
enabled: true
---

# Topic: aigc-visual (Seedream + Seedance)

Bundled topic covering BytePlus visual content generation. Both products share the ICP (creative tools that need AI image OR video generation) so we hunt as one.

## BytePlus product fit

- **Seedream 5.0** ([entity ref](../../../../shared/kb/entities/seedream-5.0-lite.md)) — text-to-image, image editing, style transfer, product photos.
- **Seedance 2.0** ([entity ref](../../../../shared/kb/entities/seedance-2-0.md)) — text-to-video, image-to-video, motion. Audio sync via `generate_audio: true`.
- Both APIs share the Ark gateway: `https://ark.ap-southeast.bytepluses.com/api/v3` for SEA traffic.

For outreach, mention whichever fits the candidate's product better. If they do both image + video, mention both.

## ICP (Ideal Customer Profile)

**All entries below must satisfy [Filter 0](../lead-philosophy.md): the company's own product/feature must expose AI image or video output to *end users*, not just to internal employees.** If image/video AI is only used internally for marketing collateral or analyst decks, it's an AI consumer — skip.

AI producers we want (in order of fit):

- **Marketing/creative SaaS shipping AI image-or-video features to their users** — social media schedulers with built-in AI generation, content tools where the customer presses a button and gets AI output. NOT companies whose marketing team uses Midjourney internally.
- **Media companies whose end-product viewers consume AI-generated video** — microdrama platforms, sports-highlight apps, news automation that ships AI clips to viewers. NOT publishers using AI internally for editorial workflow.
- **Indie creators on Replicate/Stable Diffusion** running AI image/video products with paying users — they're producers because they expose AI to a customer.

**NOT in ICP (auto-skip on Filter 0):**
- Pure AI image/video model labs (competitors — separate auto-skip)
- Companies using AI internally for marketing/sales/ops (consumers)
- Massive publishers with their own content stacks (CNN, BBC, Disney)
- "AI-curious" enterprises announcing they "are exploring AI" without a customer-facing AI feature shipped
- Consumer-only apps without API need (e.g., a one-off filter app — too small to scale into an API customer)
- **Image / video model builders (Filter 0b — added 2026-05-05)**: companies that trained their *own* image- or video-gen model. They compete at the model layer; we shouldn't sell them Seedream / Seedance.
  - Examples to skip: any "AI image gen for {vertical}" company that emphasizes "proprietary model", research-paper origin, or research-grant funding. Same logic as the FurniMesh anti-example in seed3d.
  - Edge case: a fashion-AI company that *fine-tunes* a third-party base (Stable Diffusion etc.) for fashion is still an aggregator if they don't claim a from-scratch model. Default skip if mixed signals.

**ICP target (after Filter 0a + 0b pass)**: aggregators / integrators in image and video — companies who build user-facing creative experiences by *consuming* third-party image/video APIs. They wire Seedream / Seedance / Midjourney / SDXL / Veo into a vertical product and ship it to customers.

## Search angles (rotate by day-of-week per [discovery-rotation](../discovery-rotation.md))

### Day-type A (Mon, Sat) — ProductHunt
- "AI marketing tool" recent launches
- "AI video editor" recent launches
- "AI product photo" recent launches
- Vertical sweep fallback: microdrama, fashion AI, sports highlights, eLearning publishers, webtoon platforms

### Day-type B (Tue, Sun) — Regional
- LATAM: marketing automation with AI
- MENA: creative agencies with AI services
- India: niche video tools (NOT well-known platforms)
- Eastern Europe: SaaS adding AI features

### Day-type C (Wed) — Agencies
- Clutch.co + DesignRush: agencies advertising "AI creative" or "generative AI"
- Filter to <50 employees (small agencies more likely to need API, not build)

### Day-type D (Thu) — YC / accelerators
- YC current batch + F2025: filter to media, video, content categories
- 500 Global Creators Ventures (validated high-yield)
- Antler creative-tech
- Harvard Innovation Labs

### Day-type E (Fri) — SaaS feature additions
- TechCrunch "X adds AI image/video"
- ProductHunt "adds AI" tagged launches
- Real estate AI staging/photography tools
- Fashion AI virtual try-on / lookbook tools
- E-learning platforms adding video avatars

## Negative signals (auto-skip, score → 0)

Any of these = SKIP and append to skip-list:

1. **BytePlus mention on website**: Seedream, Seedance, ByteDance, VolcEngine, Doubao, Jimeng anywhere in the site, blog, or product docs.
2. **Direct competitor**: Runway, HeyGen, Synthesia, D-ID, Pika, Luma, Kling, Sora — companies that sell the same product.
3. **Featured on "top AI image/video tools" lists** with prominent placement (>50K reach).
4. **>50K social followers + "AI" in branding** (well-known, BD already has them).
5. **Marketed as a "model" or "lab"** building their own generation tech.

## High-yield verticals (per SKILL.md Discovery Patterns)

Based on archived reflection data 2026-03-13 to 2026-04-25:

- **Microdrama / vertical video**: Vigloo, StoReel, Kami/Çizgi Studio. Hottest active vertical for Seedance.
- **Influencer marketing platforms**: nowfluence, MoonTech, InfluSense. Rarely in BD CRM.
- **Fashion AI**: Bezel, WearView, Refabric. Image + video both fit.
- **eLearning with avatar/video modules**: Mindsmith, Knowlify.
- **Webtoon/comic platforms**: Toonsquare/Tooning.

## Saturated verticals (penalty -2)

- Well-known AI platforms (all already in BD CRM).
- Companies with "AI" prominently in branding + medium funding.
- UAE marketing/advertising with >$1M funding (mixed; check carefully).
- AI-native video/image generators (competitor profile).

## Outreach angle templates

Pick one based on the candidate's primary product:

**For image-heavy candidates (e-commerce, product photos, marketing creative):**
> Saw [their image-gen feature]. We power Seedream API for [analogous customer]. Volume tiers + Asia low-latency might fit your [their use case].

**For video-heavy candidates (microdrama, sports, social video):**
> Noticed [their video product]. Seedance 2.0 does i2v and t2v at [their fps/resolution range]. Worth a 15-min look at the API?

**For both image + video candidates:**
> Saw [their AI feature]. We power both Seedream (image) and Seedance (video) for [similar customer]. Bundled volume pricing might fit your [specific use case].