# channel-github — usage

## Invocation

- By a session: `/channel-github setup`, `/channel-github rank <question>`,
  `/channel-github pending`, `/channel-github retag`. `setup` and `retag`
  write only on the operator's yes; `rank` and `pending` write nothing.
- By ticket: a harvest job's `process` step is `/channel-github ticket=<id>`;
  its `harvest` and a routines job's `routine` are scripts the runner starts,
  never typed.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-github/scripts/<script> …`
at the wiki root. `<capture_dir>` is the ticket's own, wiki-relative,
verbatim.

| script | step | argv |
| :--- | :--- | :--- |
| `harvest.py` | harvest | `ticket=<id>`, not a flag; started by the runner |
| `page.py prepare` | process, first | `<capture_dir> --ticket <id>` |
| `page.py write` | process, last | `<capture_dir> --ticket <id> --from judgment.json [--readme full\|excerpt\|none]`; a bare `--from` name is read from the capture directory |
| `lists.py` | routine | `[--only <words>] ticket=<id>`; started by the runner, the entry's `args` first |
| `catalog.py census` | setup | `[--top N]` |
| `catalog.py scan` | retag | none |
| `catalog.py rank` | rank | `[--tag T]… [--any-tag A,B]… [--text WORDS] [--all-words] [--starred] [--min-stars N] [--paths-from FILE\|-] [--sort S] [--limit N] [--format table\|compact\|json]` |
| `catalog.py preview` | setup | `[--only <words>]`: the list pages, printed, never written |
| `catalog.py pending` | pending | none |

`door.py` and `catalog.py`'s functions are imported by the others; `door.py`
is never run.

## Routine args

A routines job's entry `args` reach `lists.py` before `ticket=<id>`:
`--only <words>` regenerates only the list pages whose title contains them.
Safe unattended.

## Knobs

- `options.select` (a harvest job's, required there): the selectors.
- `options.max_captures`, `jump_abs`, `jump_pct`, `refresh_days`,
  `include_forks`, `include_archived`, `search_limit`: the harvest's
  re-capture rules (SKILL.md, harvest).
- `requires.credentials.routes.github` is `optional`: the `github` route raises
  the rate limit; unmapped, harvest runs keyless.
- The `channel-github` overlay: categories, README mode, junk rules.
- `references/lists.json`: the lists, the weights, where repo pages are read.
