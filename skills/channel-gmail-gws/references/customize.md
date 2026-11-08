# channel-gmail-gws — customizing this skill

Nothing here needs an edit to the unit. Three dials, all the wiki's:

1. **The profile** — this unit's policy overlay: who matters (`$vips`,
   `$family`, `$waiting`), what is noise (`$noise`, `$receipts`,
   `$newsletters`), the draft voice, working hours and hard rules. Both faces
   read it: the process step to junk and categorize, the attended modes to
   classify and draft. `/channel-gmail-gws setup` runs the interview
   (`{{@brain-cli-ops}} reference channel-gmail-gws/profile`); `{{@brain-cli-ops}} policy
   get channel-gmail-gws` reads it back.
2. **A job's mechanical filters** — `options.lookback_days`, `options.cap`,
   `options.exclude_labels`, `options.exclude_senders`, per mailbox, asked at
   `jobs add` and changed with `{{@brain-cli-ops}} jobs edit <slug>
   options.exclude_senders=@noisy.example`. Cadence is the job's `every`
   (default `1d`).
3. **A playbook of the wiki's own** — a `## Playbook: <name>` section in the
   overlay, in the shape `{{@brain-cli-ops}} reference
   channel-gmail-gws/playbook-template` gives, run with `--playbook <name>`.
   A shipped playbook's name in the overlay wins over the shipped one.

Questions to ask the operator the first time:

- Which senders and domains are VIPs? Family? Pure noise? Receipts?
- Who are they waiting on right now?
- Should `clean` ever archive unread mail? (default: only `$noise`)
- Label names, and may the attended modes create missing ones?
- Draft voice: sign-off, length, anything never to promise.
- Working hours, and what "urgent" means outside them.

Each answer is offered back as the overlay (`{{@brain-cli-ops}} policy set
channel-gmail-gws`, the whole text on stdin, read first), performed only on
the operator's yes.

## Sandbox

The manifest's `sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:gmail-gws`. `skills install` validates
that template and writes it as the unit's `sandbox.jsonc`; `skills enable`
shows what each stage adds to its stock base and asks. What the stages
reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/gmail-gws.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
