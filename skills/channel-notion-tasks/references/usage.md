# channel-notion-tasks — usage

Invoked `/channel-notion-tasks ticket=<id> stage=<harvest|process>`. The step
is the `stage` that `tickets open <id>` answers. One invocation serves one
workspace (`options.workspace`) and one day directory; it takes no other
argument.

## Scripts

Both run as `llm-wiki-ops run ops/skills/channel-notion-tasks/scripts/<script> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| script | step | argv |
| :--- | :--- | :--- |
| `write_items.py since` | harvest, first | `<capture_dir> --ticket <id> [--lookback-days N]` (default 14); prints `since`, `first_pull`, `cursor_ignored` |
| `pull.py` | harvest | `<capture_dir> --workspace <options.workspace> --since <since> --database <id>… [--deadline-seconds N]`; writes `pull.json`; deadline defaults to 900 s; exit 3 pulled nothing |
| `write_items.py write` | harvest, last | `<capture_dir> --ticket <id> [--from FILE] [--cap N] [--partial WHY] [--database ID]… [--exclude-status S]…`; or `--failed WHY --missing HOST URL denied\|timeout\|auth\|error` |
| `write_items.py ledger` | process | `<capture_dir> --ticket <id> [--from FILE] [--partial WHY]` |

`--from` defaults to `pull.json` (`write`) and `lines.json` (`ledger`). `pull.py`
alone calls `ntn`, read-only. `-h` after a path lists the rest.

## Knobs

- `watch.inputs.workspace` (required) lands as `options.workspace`; the pull
  refuses a token whose workspace differs.
- The databases are passed as `--database` on `pull.py` (SKILL.md, harvest).
- `process.exclude_rules` feeds the junk rules (SKILL.md, process).
- `requires.credentials.notion` is `required`: the vault entry the `notion`
  route spends. `ntn` must be on PATH.
