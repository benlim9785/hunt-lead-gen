# leads-hunt-pack

Portable BytePlus AE lead-generation skill pack for OpenClaw. Lark-chat-driven, no dashboard, ~30-min conversational onboarding.

## Install

In your Lark DM with your OpenClaw agent:

> **clawdia, install this skill pack: `https://github.com/benlim9785/leads-hunt-pack`**

That's it. OpenClaw fetches all 5 skills and registers them.

Then:

> **clawdia, set me up for leads hunt**

The setup wizard walks you through Lark binding check, LinkedIn login, BD Sales Nav SSO, kb.md init, topic scaffolding, and cron registration (~30 min).

## Skills

| Skill | Purpose |
|---|---|
| `leads-hunt` | Daily 4-phase pipeline (SSO → discover → dedup → digest), cron-scheduled |
| `leads-hunt-outreach` | On-demand outreach drafting from kb.md row + your voice file |
| `leads-hunt-add-target` | Interactive scaffolding for new topic `.md` files |
| `leads-hunt-setup` | First-run wizard: Lark check, LinkedIn login, kb.md init |
| `leads-hunt-voice` | Conversational voice-file management (add sample / set rhythm / show / reset) |

## After setup

Daily Lark digest fires at 09:30 server-tz. To act on it, ask your agent in chat:

- *"draft outreach for &lt;company&gt;"* → `leads-hunt-outreach`
- *"add this to my voice: &lt;paste a real message&gt;"* → `leads-hunt-voice`
- *"add a new target topic"* → `leads-hunt-add-target`

## State location

Per-AE state lives at `<openclaw_workspace>/leads-hunt/`:
- `kb.md` — knowledge base (markdown, H2 sections)
- `style.md` — outreach voice file
- `browser-profile/` — Playwright Sales Nav session
- `.env` — `LARK_*`, `LINKEDIN_*`, `BYTEDANCE_CORP_*`

## Prerequisites (one-time, before pack install)

- OpenClaw installed and running
- `openclaw onboard` completed with your Lark app bound

## License

MIT — see [LICENSE](LICENSE).

## Origin

Greenfield port of `clawhunt-*` Hermes skills (Ben Lim's daily flow). ClawMander-coupled paths replaced with text-file `kb.md`. Voice exemplars stripped to blank-slate template.
