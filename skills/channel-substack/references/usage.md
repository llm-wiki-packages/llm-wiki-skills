# channel-substack — usage

Invoked `/channel-substack ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One harvest ticket captures a whole archive; one process ticket writes one post.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-substack/scripts/<script> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| script | step | argv |
| :--- | :--- | :--- |
| `enumerate_archive.py` | harvest | `--capture-dir <capture_dir> --ticket <id> [--max-leaves N] [--limit N] [--out FILE]`; writes `leaves.json` |
| `capture_posts.py` | harvest | `--capture-dir <capture_dir> [--fetch] [--deadline-minutes M] [--only URL] [--plan FILE]`; takes no `--ticket` |
| `capture_posts.py --report` | harvest, last | `--capture-dir <capture_dir> --report --ticket <id> [--missing URL=WHY]…` |
| `to_markdown.py` | process | `<capture_dir>/page.html --out - --selector .available-content --base-url URL` |

The process report is `llm-wiki-ops --json tickets update <id> stage=process status=ok written_from=written.json` (SKILL.md, process).

`WHY` is `denied`, `timeout`, `auth` or `error`. `--max-leaves` defaults to
200 and `--deadline-minutes` to 20. `-h` after a path lists the rest.

## Knobs

- No `watch.inputs`. The scripts read `harvest.scope` (must be `domain`),
  `harvest.access` (`free` or `licensed`), `harvest.exclude_urls`,
  `harvest.max_age` (as `min_date`), `known[]` and a refresh's `resource` off
  the ticket; no flag stands in for them. `harvest.assets` is `reference` by
  default (SKILL.md "Media").
- `process.exclude_rules` and `options` are applied first at process.
- `requires.file` is `optional`: a `licensed` job binds a credential file
  (SKILL.md "Auth").
