# channel-gmail — customizing this skill

Ask the lookback window for the FIRST pull (default 7d) and any
mechanical filters — Gmail labels and senders to exclude beyond the
defaults. They go into the installed SKILL.md's `### harvest` section, and
they are the WIKI's, applying to every mailbox this skill pulls. Ask what
the mailbox's junk is, too: the junk rules and the line each message gets
are the `### process` section's, and equally the wiki's to write.

Ask the pull cadence (default daily) — that becomes `every` on the
watch; the manifest pre-answers `1d`.

Customized is the point: writing the operator's filters into `## Stages`
makes `skills ls` report the skill `customized`. That is configuration the
wiki owns, not drift to repair — say so in your report so nobody "fixes"
it with `skills install --force`.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:gmail`.
`skills install` validates that template and writes it as the unit's
`sandbox.jsonc`; `skills enable` shows what each stage adds to its stock
base and asks. What the stages reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/gmail.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
