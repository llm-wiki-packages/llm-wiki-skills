# channel-circle — usage

Invoked `/channel-circle ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One harvest ticket walks a whole section; one process ticket writes one lesson.

## Scripts

Each runs as `{{@brain-cli-ops}} run ops/skills/channel-circle/scripts/<script> …`
at the wiki root. `<capture_dir>` is the ticket's own, wiki-relative,
verbatim; a lesson is named by `--leaf <n>`, its `order` in `plan.json`, never
by url.

| script | argv |
| :--- | :--- |
| `capture_lesson.py` | `. --out <capture_dir> --ticket <id>` for the ticket's target; `. --plan <capture_dir>/plan.json --leaf <n> --ticket <id>` for one lesson; either takes `[--headed] [--timeout-ms N]` (45000) |
| `section_plan.py plan` | `<capture_dir> --ticket <id> [--budget-s SECONDS]` |
| `section_plan.py detect` | `<capture_dir> --leaf <n>` |
| `section_plan.py record` | `<capture_dir> --leaf <n>` |
| `section_plan.py report` | `<capture_dir> --ticket <id> [--missing-leaf <n> <why>]… [--missing-host <host> <why>]… [--auth-expired] [--gone] [--reason TEXT] [--stage harvest\|process] [--written-from FILE]` |
| `outage_probe.py` | `. --ticket <id> [--settle-ms 8000]`; always exits 0 and prints a JSON verdict |
| `to_markdown.py` | `<capture_dir>/page.html --out <capture_dir>/page.md` |

`<why>` is `denied`, `timeout`, `auth` or `error`. The order of the calls is
SKILL.md, harvest.

## Knobs

- No `watch.inputs`. The ticket's `harvest.scope` (default `section`: the job's
  url must be the space root, `/c/<slug>`), `harvest.access`
  (`licensed`), `harvest.assets` (`download`), `harvest.exclude_urls`,
  `min_date` and `known[]` are read, never re-asked. `min_date` is not applied
  (SKILL.md "Dates").
- `process.exclude_rules` and `options` are applied first at process.
- `requires.credentials.dir` is `required`: the Chrome profile for the domain (SKILL.md
  "Auth").
