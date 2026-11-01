# channel-blackboard — customizing this skill

Most institutions serve Blackboard on their own domain
(`learn.example.edu`), not `*.blackboard.com`. Record the institution's host
in the installed SKILL.md under a "Sites" heading, and add `host:<domain>`
to the installed copy's `manifest.json` `keywords`, so `{{@brain-cli-ops}}
skills search <domain>` answers from the wiki's copy.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:blackboard`.
What the stage reaches, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/blackboard.md
```

The session runs `bb.py` itself, so the institution's own host joins the
`routine` stage's `allow_domain` only if a scheduled run is ever added.
