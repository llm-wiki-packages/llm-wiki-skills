# channel-youtube-watch-local — customizing this skill

Ask whether the default question fits this wiki. `references/question.md` is
the prompt every video gets; a wiki that wants something else says so with
`enrich.options.question=` on the job, or a policy overlay for every job
(`{{@brain-cli-ops}} reference policy-overlays`). Ask what frame cap suits the
videos: the default 24 reads a lecture coarsely and costs a session's worth of
images.

## Sandbox

The manifest's `sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:youtube-watch-local`. `skills install`
validates that template and writes it as the unit's `sandbox.jsonc`;
`skills enable` shows what each stage adds to its stock base and asks. What
the stages reach, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/youtube-watch-local.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`.
