# leads-hunt-pack

Daily lead-gen for BytePlus AEs. Runs on OpenClaw, driven entirely from Lark chat.

## Prerequisites

You need OpenClaw installed and bound to your Lark app **before** installing this pack. If you don't have OpenClaw yet:

```bash
# install OpenClaw (macOS / Linux)
curl -fsSL https://openclaw.ai/install.sh | sh

# bind your Lark app + complete first-run setup
openclaw onboard
```

After `openclaw onboard` finishes, you have an OpenClaw agent reachable from Lark. That's the "clawdia" you'll DM in the next step.

Full OpenClaw install docs: <https://docs.openclaw.ai/install>

## Install + first run

In your Lark DM with your OpenClaw agent:

> **clawdia, install this skill pack: `https://github.com/benlim9785/hunt-lead-gen`**

OpenClaw fetches and registers all 5 skills.

Then:

> **clawdia, set me up for leads hunt**

The `leads-hunt-setup` wizard runs (~25 min): workspace init, LinkedIn login, BD Sales Nav SSO, digest target chat, kb.md init, topic scaffolding, cron registration. After it completes, your daily digest fires at 09:30 server-tz.

## What's in the pack

5 skills, all chat-driven, no dashboard:

- `leads-hunt-setup` — one-time onboarding wizard (run once, after install)
- `leads-hunt` — daily Sales Nav discovery + Lark digest delivery (cron-fired)
- `leads-hunt-outreach` — on-demand outreach drafting in your voice (`"draft outreach for <company>"`)
- `leads-hunt-add-target` — add new ICP topics over time (`"add a target: <description>"`)
- `leads-hunt-voice` — teach the agent your writing style (`"add to my voice: <paste>"`)

## License

MIT — see [LICENSE](LICENSE).
