# channel-youtube — customizing this skill

Ask whether videos should be downloaded (`harvest.assets=download`) or kept as
cloud references (`harvest.assets=reference` — captions/transcript + a
watch-at-source link; the default worth suggesting for YouTube, since
the source rarely rots and video files are heavy).

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:youtube`.
`skills install` validates that template and writes it as the unit's
`sandbox.jsonc`; `skills enable` shows what each stage adds to its stock
base and asks. What the stages reach, and why:

```sh
llm-wiki-ops reference llm-wiki-packages/llm-wiki-skills:sandboxes/youtube.md
```

Widening is a committed edit to the unit's `sandbox.jsonc` followed by
`skills enable`. `process` extends the stock `process` base, which opens no
host.
