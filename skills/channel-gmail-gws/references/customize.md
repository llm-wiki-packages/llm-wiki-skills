# channel-gmail-gws — customizing this skill

Nothing here needs an edit to the unit. Three dials, all the wiki's:

1. **The profile** — this unit's policy overlay: who matters (`$vips`,
   `$family`, `$waiting`), what is noise (`$noise`, `$receipts`,
   `$newsletters`), the draft voice, working hours and hard rules. Both faces
   read it: the process step to junk and categorize, the attended modes to
   classify and draft. `/channel-gmail-gws setup` runs the interview
   (`llm-wiki-ops reference channel-gmail-gws/profile`); `llm-wiki-ops policy
   get channel-gmail-gws` reads it back.
2. **A job's mechanical filters** — `options.lookback_days`, `options.cap`,
   `options.exclude_labels`, `options.exclude_senders`, per mailbox, asked at
   `jobs add` and changed with `llm-wiki-ops jobs edit <slug>
   options.exclude_senders=@noisy.example`. Cadence is the job's `every`
   (default `1d`).
3. **A playbook of the wiki's own** — a `## Playbook: <name>` section in the
   overlay, in the shape `llm-wiki-ops reference
   channel-gmail-gws/playbook-template` gives, run with `--playbook <name>`.
   A shipped playbook's name in the overlay wins over the shipped one.

Questions to ask the operator the first time:

- Which senders and domains are VIPs? Family? Pure noise? Receipts?
- Who are they waiting on right now?
- Should `clean` ever archive unread mail? (default: only `$noise`)
- Label names, and may the attended modes create missing ones?
- Draft voice: sign-off, length, anything never to promise.
- Working hours, and what "urgent" means outside them.

Each answer is offered back as the overlay (`llm-wiki-ops policy set
channel-gmail-gws`, the whole text on stdin, read first), performed only on
the operator's yes.

## Sandbox

`stages.harvest.sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:gmail-gws/gmail-gws.harvest`:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/gmail-gws/gmail-gws.harvest.md
```

`/llm-wiki:enable channel-gmail-gws` reviews and binds it. `process` names
no sandbox and runs with no network.
