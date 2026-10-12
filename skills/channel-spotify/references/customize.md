# channel-spotify — customizing this skill

## Sandbox

`stages.harvest.sandbox_ref` is
`llm-wiki-packages/llm-wiki-skills:spotify/spotify.harvest`. What the stage reaches,
and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:references/sandboxes/spotify/spotify.harvest.md
```

`/llm-wiki:sandbox channel-spotify` reviews it, and `/llm-wiki:enable
channel-spotify` binds the stage. **Reuse the `spotify-harvest` sandbox
`skills install` wrote; never write a `channel-spotify-harvest` from the
snippet.** The `spotify` route is the reference's `## Machine` block, which
install puts in that sandbox's `machine.allow` and a sandbox written from
`## Profile` alone lacks, and the manifest declares
`requires.credentials.spotify`: `skills enable` refuses a stage bound to a
sandbox that carries no `spotify` route. `process` names no sandbox and runs
with no network.
