# channel-parentsquare — customizing this skill

Ask which schools the account should pull (blank pulls every school it lists)
and how many days of feed each pull reads (default 3); they are the watch's
`options.schools` and `options.lookback_days`, set on `jobs add`.

Ask what the family's junk is: the junk rules and the line each post gets are
the `### process` section's, and the WIKI's to write. Writing them into the
installed SKILL.md makes `skills ls` report the skill `customized`. That is
configuration the wiki owns, not drift to repair — say so in your report so
nobody "fixes" it with `skills install --force`.

Ask the pull cadence (default daily) — that becomes `every` on the watch; the
manifest pre-answers `1d`.

## Sandbox

The manifest's `sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:parentsquare`. `skills install` validates
that template and writes it as the unit's `sandbox.jsonc`; `skills enable`
shows what each stage adds to its stock base and asks. What the stages
reach, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:sandboxes/parentsquare.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
