# channel-circle — customizing this skill

Circle communities run on `*.circle.so` **or their own custom domain**, but
a custom-domain community still renders Circle's own uniform chrome — so
ONE installed copy normally serves every community this wiki watches, with
one watch per community.

Ask which community this wiki watches (the `*.circle.so` domain or the
custom domain fronting it) and record it in the installed SKILL.md under
a "Watched communities" heading — the skill body is wiki-owned. For a
custom-domain community, also add `host:<domain>` to the installed copy's
`manifest.json` `keywords`, so `skills search <domain>` answers from the
wiki's copy directly. The harvest slice reaches that host as the ticket's
own; the sandbox needs no entry for it.
There is no second copy to install: identity is the JOB's slug, so two
communities are two jobs on this one skill, each under its own heading
here.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:circle`.
`skills install` validates that template and writes it as the unit's
`sandbox.jsonc`; `skills enable` shows what each stage adds to its stock
base and asks. What the stages reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/circle.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
