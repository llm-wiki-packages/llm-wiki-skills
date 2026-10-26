# channel-substack — customizing this skill

Ask which newsletter(s) this wiki watches (domain or archive URL) and a
slug for each, and record them in the installed SKILL.md under a
"Watched newsletters" heading — the skill body is wiki-owned.

Ask free-only vs licensed. Free needs no auth; licensed needs a
Playwright storage state for the newsletter's own domain (custom-domain
newsletters may not share substack.com cookies). Licensed also needs the
skill to DECLARE a credential — see `{{@brain-cli-ops}} reference channel-substack/enable` for the steps
and their cost.

Ask for an age floor (e.g. only posts from the last 3 months) — that
becomes `harvest.max_age` on the job, and rides each ticket as `min_date`.

## Sandbox

The manifest's `sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:substack`. `skills install` validates
that template and writes it as the unit's `sandbox.jsonc`; `skills enable`
shows what each stage adds to its stock base and asks. What the stages
reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/substack.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
