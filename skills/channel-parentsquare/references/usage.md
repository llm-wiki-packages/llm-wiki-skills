# {{@brain-unit}} — usage

Invoked `/{{@brain-unit}} ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One invocation serves one account and one day directory.

## Scripts

Each runs as `{{@brain-cli-ops}} run ops/skills/{{@brain-unit}}/scripts/<script> …`.
`keys.py` takes a draft, a JSON file the session wrote with its file-writing tool: served text never rides a command line.
The harvest reads through the `parentsquare` MCP server the sandbox declares; `ledger.py` writes the day's page with the front door's verbs.

| script | step | further argv |
| :--- | :--- | :--- |
| `keys.py notice` | harvest | `<draft.json>` holding `school_id`, `title`, `date`; prints `ps-notice-<school_id>-<12 hex of sha1(title\|date)>` |
| `keys.py stamp` | harvest | `<draft.json>` holding `date` and `id`; `[--now MS] [--day-dir DIR]`; prints 13-digit epoch milliseconds from an ISO-8601, epoch or month-name date, else the stamp of the `id`'s file in `DIR/items/`, else the pull's clock |
| `ledger.py` | process | `<capture_dir> --ticket <id> [--from lines.json] [--partial REASON]`; reads `items/*.json` and the rows in `lines.json` (only for items judged: `junk`, or a `line`; an `id` no item carries is `unmatched` and makes the report `partial`), writes `<dest>/<YYYY-MM-DD>.md` whole, `written.json`, and the report; prints the counts as JSON |

## Knobs

- `watch.inputs.schools` lands as `options.schools`: comma-separated school ids, blank for every
  school the account lists.
- `watch.inputs.lookback_days` lands as `options.lookback_days` (default 3): the feed history
  each pull reads.
- `process.exclude_rules` feeds the junk rules (SKILL.md, process).
- `requires.credentials.env` is `PS_USERNAME` and `PS_PASSWORD`, both required: the machine's
  binding, never read by the unit (`references/enable.md`).
