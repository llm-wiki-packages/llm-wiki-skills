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

`/llm-wiki:sandbox channel-notion-tasks` reviews it into a wiki sandbox, and
`/llm-wiki:enable channel-notion-tasks` binds the stage. The wiki sandbox
holds only the `## Profile` block. A harvest also needs this machine's allow
fragment for the `notion` credential route (`## Machine`), applied when the
operator enables the sandbox. `process` names no sandbox and runs with no
network.
