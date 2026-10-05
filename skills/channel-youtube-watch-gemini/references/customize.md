# channel-youtube-watch-gemini — customizing this skill

Ask whether the default question fits this wiki. `references/question.md` is
the prompt every video gets; a wiki that wants something else says so with
`enrich.options.question=` on the job, or a policy overlay for every job
(`llm-wiki-ops reference policy-overlays`).

## Sandbox

`stages.enrich.sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:gemini/gemini.enrich`. What the stage
reaches, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/gemini/gemini.enrich.md
```

`/llm-wiki:sandbox channel-youtube-watch-gemini` reviews it into a wiki
sandbox, and `/llm-wiki:enable channel-youtube-watch-gemini` binds the stage.
