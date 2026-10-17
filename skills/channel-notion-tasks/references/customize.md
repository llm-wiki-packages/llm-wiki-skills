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

`stages.harvest.sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:notion/notion.harvest`. What the stage
reaches, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/notion/notion.harvest.md
```

`/llm-wiki:sandbox channel-notion-tasks` reviews it, and
`/llm-wiki:enable channel-notion-tasks` binds the stage. **Reuse the
`notion-harvest` sandbox `skills install` wrote; never write a
`channel-notion-tasks-harvest` from the snippet.** The `notion` route is the
reference's `## Machine` block, which install puts in that sandbox's
`machine.allow` and a sandbox written from `## Profile` alone lacks, and
the manifest declares `requires.credentials.routes.notion` `"required"`: `skills
enable` refuses a stage bound to a sandbox that carries no `notion` route.
Its probe, `ntn whoami`, runs at `sandboxes enable notion-harvest` and
spends the wiki's vault entry `notion`, so on each machine name the vault
and store the token BEFORE `/llm-wiki:enable` enables it (steps 2 and 3 of
`llm-wiki-ops reference channel-notion-tasks/enable`). No route in a harness
profile: the route is the stage's. `process` names no sandbox and runs with
no network.
