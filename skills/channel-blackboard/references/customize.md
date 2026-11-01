# channel-blackboard — customizing this skill

Most institutions serve Blackboard on their own domain
(`learn.example.edu`), not `*.blackboard.com`. Record the institution's host
in the installed SKILL.md under a "Sites" heading, and add `host:<domain>`
to the installed copy's `manifest.json` `keywords`, so `{{@brain-cli-ops}}
skills search <domain>` answers from the wiki's copy.

## Per job

- `options.timezone`: the IANA zone due dates and post times read in.
- `options.files`: `download` (the default) or `skip`.
- `transcribe.options.when`: `always` re-speaks a video that came with
  captions; `/{{@brain-plugin}}:add` changes it.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:blackboard`.
What the stage reaches, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/blackboard.md
```

The institution's own host is the job's target and joins the harvest
slice's egress at dispatch, so it needs no entry there.
