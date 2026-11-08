# channel-spotify — customizing this skill

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:spotify`.
`skills install` validates that template and writes it as the unit's
`sandbox.jsonc`; `skills enable` shows what each stage adds to its stock
base and asks. What the stages reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/spotify.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.

The `spotify` route is on the template's harvest stage; nothing maps it
until the operator does (`{{@brain-cli-ops}} reference channel-spotify/enable`),
and unmapped, every capture is keyless.
