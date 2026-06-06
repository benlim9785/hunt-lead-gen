# How to teach your voice over time

Voice quality is a function of iteration. Empty `style.md` produces flat, generic outreach. After 5-10 real samples and a handful of do/don't bullets, the drafter starts sounding like you. Here's how to get there without spinning your wheels.

## Start with examples, not rules

The single highest-leverage move on day one: paste 3-5 real outreach messages you've sent that got replies. Don't try to articulate your style in prose first. The model picks up rhythm, vocabulary, and structure from examples better than from any abstract description.

Use:
> "add this to my voice: hey, saw your post about <X>. we built <Y> for exactly this. want me to send a sandbox link?"

Date it. Optionally annotate ("replied in 4hrs", "led to demo"). Repeat with 4 more.

## Articulate rules only after the model gets it wrong

Once you have a handful of samples, ask Clawdia to draft an outreach message for a real lead. Read the output. If it feels off, *now* you have something concrete to react to:

- Drafter used an em-dash you'd never use → "never say em-dash, use comma instead"
- Drafter wrote "I hope this finds you well" → "add to my don'ts: hope this finds you well"
- Drafter was too long → set rhythm: "max 3 sentences, under 50 words total"

This is much higher signal than guessing rules in a vacuum.

## Be concrete about rhythm

Avoid vague directives:
- ❌ "be casual"
- ❌ "sound natural"
- ❌ "match my energy"

Write concrete patterns the model can actually follow:
- ✅ "sentences under 12 words, no semicolons, max one emoji per message, no em-dashes"
- ✅ "open with lowercase 'hey, ' — never 'hi' or 'hello'"
- ✅ "close with a single yes/no question, never 'let me know your thoughts'"

## Periodically clean up

After 20+ samples and a couple dozen do/don't bullets, your style.md gets messy. Duplicates creep in, contradictions appear, old rules go stale. Ask:

> "clean up my voice"

Clawdia will read the whole file, propose a deduped/clarified version, and ask before writing. You stay in control; the agent just does the editing chore.

## Don't paste samples that aren't yours

The point of the file is matching YOUR idiom. If you paste a colleague's message because it sounds good, the drafter will sound like them, not you. That defeats the system. Use only messages you actually wrote.

## When to reset

Reset is rare. Reasons to do it:
- You're switching markets and your old voice doesn't fit the new ICP.
- The file got contaminated with experiments and is hard to clean up.
- You want a clean slate.

`voice.py reset --confirm-twice` saves a `style.md.bak-<timestamp>` first, so reset is recoverable. The agent will ask twice before doing it.

## Watch for drift

Re-read your style.md every few weeks. Do the do/don't bullets still reflect how you write today? Are the samples still representative of your best work? Voice evolves; the file should too.
