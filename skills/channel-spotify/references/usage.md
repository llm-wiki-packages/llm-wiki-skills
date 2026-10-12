# channel-spotify — usage

Invoked `/channel-spotify ticket=<id> stage=<harvest|process>`. The step is the
`stage` that `tickets open <id>` answers; it takes no other argument. One job
is one entity url (playlist, show, episode, album or audiobook).

## Script

`scripts/spotify.py <subcommand> …`, run as
`llm-wiki-ops run ops/skills/channel-spotify/scripts/spotify.py …` at the wiki
root. `<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| subcommand | step | argv |
| :--- | :--- | :--- |
| `capture` | harvest | `--capture-dir <capture_dir> --ticket <id> [--market US] [--keyless] [--no-audio] [--entity-json FILE]`; exit 4 no audio resolved, exit 3 not found |
| `report` | harvest, last; process | `--capture-dir <capture_dir> --ticket <id> [--missing URL=WHY]…`; at process add `--written-from FILE` |
| `process` | process | `--capture-dir <capture_dir> --ticket <id>`; prints the page it wrote |
| `meta` | utility | `<url> [--market US] [--keyless]`; normalized entity JSON |
| `resolve-feed` | utility | `<show-or-episode-url> \| --show-name NAME`, with `[--market US] [--limit N]`; the public RSS feed |

`WHY` is `denied`, `timeout`, `auth` or `error`. Assets are downloaded between
`capture` and `report` with the plugin's `scripts/assets.py` (SKILL.md,
harvest). `-h` after the path lists the rest.

## Knobs

- No `watch.inputs`. The ticket's `harvest.assets` (`download`,
  `download-audio`, `reference`) picks the asset arguments; `min_date`
  (from `harvest.max_age`) drops older items; `harvest.refresh` is how new
  episodes arrive.
- `process.exclude_rules` is a case-insensitive substring of the entity's name
  or url. `on_change`, `embeds`, `bundle_media` and `options` are not acted on.
- The harvest sandbox's `spotify` route carries the app's client credentials;
  without it a capture is keyless and the item list may be truncated.
