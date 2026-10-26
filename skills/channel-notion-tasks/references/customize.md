# channel-notion-tasks — customizing this skill

Ask which Notion databases hold the operator's tasks and record their
database ids in the installed SKILL.md's `### harvest` "Mechanical filters":
harvest queries only these, so a first pull needs at least one. Record them
along with the lookback window for the FIRST pull (default 14d) and any
statuses to exclude (e.g. Archived). These belong in the skill, not the
watch entry.

Ask the pull cadence (default daily) — that becomes `every` on
the watch.

Customized is the point: writing the operator's databases and filters into
SKILL.md makes `skills ls` report the skill `customized`. That is
configuration the wiki owns, not drift to repair — say so in your report
so nobody "fixes" it with `skills install --force`.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:notion`.
`skills install` validates that template and writes it as the unit's
`sandbox.jsonc`; `skills enable` shows what each stage adds to its stock
base and asks. What the stages reach, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:sandboxes/notion.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.

The `notion` route is on the template's harvest stage, and the manifest
declares `requires.credentials.routes.notion` `"required"`. The template's
probe, `ntn whoami`, runs after the yes at `skills enable` and spends the
wiki's vault entry `notion` through the mapped route, so on each machine name
the vault, store the token and map the route BEFORE `/llm-wiki:enable` (steps 2 and 3 of `llm-wiki-ops reference
channel-notion-tasks/enable`). No route in a harness profile: the route is
the stage's.
