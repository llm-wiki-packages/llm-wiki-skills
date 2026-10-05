# channel-youtube-watch-local — customizing this skill

Ask whether the default question fits this wiki. `references/question.md` is
the prompt every video gets; a wiki that wants something else says so with
`enrich.options.question=` on the job, or a policy overlay for every job
(`llm-wiki-ops reference policy-overlays`). Ask what frame cap suits the
videos: the default 24 reads a lecture coarsely and costs a session's worth of
images.

## Sandbox

`stages.enrich.sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:youtube-local/youtube-local.enrich`. What
the stage reaches, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/youtube-local/youtube-local.enrich.md
```

`/llm-wiki:sandbox channel-youtube-watch-local` reviews it into a wiki
sandbox, and `/llm-wiki:enable channel-youtube-watch-local` binds the stage.
