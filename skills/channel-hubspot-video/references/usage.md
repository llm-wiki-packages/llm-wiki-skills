# channel-hubspot-video — usage

Invoked `/channel-hubspot-video ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One harvest ticket captures a whole section as bytes; one process ticket writes one capture.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-hubspot-video/scripts/<script> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim. A page is named
by `--leaf <n>`, its index in `plan.json`, never by url.

| script | argv |
| :--- | :--- |
| `leaves.py plan` | `<capture_dir> --urls <file> [--urls <file>]… --ticket <id> [--limit N] [--budget-minutes M] [--sites FILE]` |
| `leaves.py next` | `<capture_dir>` |
| `leaves.py assets` | `<capture_dir> --leaf <n>` |
| `leaves.py record` | `<capture_dir> [--leaf <n>] [--media-file FILE] [--no-media]` |
| `leaves.py report` | `<capture_dir> --ticket <id> [--missing-leaf <why> <n>]… [--missing-host <why> <host>]… [--reason TEXT] [--failed] [--gone] [--skipped] [--written-from FILE]` |
| `capture_hubspot_video.py render` | `--capture-dir <capture_dir> --leaf <n> [--ticket <id>] [--timeout MS] [--settle MS] [--headed]` |
| `capture_hubspot_video.py patch-assets` | `<assets.json> --meta <meta.json>` |
| `to_markdown.py` | `<capture_dir>/page.html --selector S --drop-selector S… --title-selector S --base-url URL` |

`<why>` is `denied`, `timeout`, `auth` or `error`. The order of the calls is
SKILL.md, harvest and process.

## Knobs

- No `watch.inputs`. The ticket's `harvest.scope` (default `section`: point the
  job at the section root), `harvest.assets` (`download`; `download-audio`
  suits a transcript-only job), `harvest.exclude_urls`, `min_date`, `known[]`
  are read, never re-asked. The unit's defaults also set the job's
  `transcribe.options.when` (`always`) and `diarize`; no script here reads
  them, the transcribe stage does.
- `process.embeds` and `process.exclude_rules` apply at process.
- `references/sites.json`, in this wiki's copy, holds the site's selectors
  keyed by host (SKILL.md "Content extraction").
