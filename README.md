# leads-hunt-pack

A portable BytePlus AE lead-generation skill pack for OpenClaw.

Five skills, Lark-chat-driven, runs on any AE's OpenClaw workspace with their own LinkedIn Sales Nav, BD-corp creds, and Lark bot. Replaces a per-AE 3-5 day setup with a ~30 minute conversational onboarding.

## Skills

| Skill | Purpose |
|---|---|
| `leads-hunt` | Daily 4-phase pipeline (SSO → discover → dedup → digest), cron-scheduled via OpenClaw |
| `leads-hunt-outreach` | On-demand outreach drafting from kb.md row + voice file |
| `leads-hunt-add-target` | Interactive scaffolding for new topic .md files |
| `leads-hunt-setup` | First-run wizard: Lark check, LinkedIn login, kb.md init |
| `leads-hunt-voice` | Conversational voice-file management — add/set/show |

## Install (per AE)

```bash
# Prereq: OpenClaw installed, `openclaw onboard` completed (Lark bound)
git clone https://github.com/benlim9785/leads-hunt-pack ~/leads-hunt-pack
cd ~/leads-hunt-pack
for s in leads-hunt leads-hunt-outreach leads-hunt-add-target leads-hunt-setup leads-hunt-voice; do
  openclaw skills install "./$s"
done
```

Then in Lark: *"clawdia, set me up for leads hunt"* → setup wizard runs.

## State location

Per-AE state lives at `<openclaw_workspace>/leads-hunt/`:
- `kb.md` — knowledge base (markdown, H2 sections)
- `style.md` — outreach voice file (managed via `leads-hunt-voice`)
- `browser-profile/` — Playwright Sales Nav session
- `.env` — `LARK_*`, `LINKEDIN_*`, `BYTEDANCE_CORP_*`

## License

MIT — see [LICENSE](LICENSE).

## Origin

Greenfield port of `clawhunt-*` Hermes skills (Ben Lim's daily flow). ClawMander-coupled paths replaced with text-file `kb.md`. Voice exemplars stripped to blank-slate template.
