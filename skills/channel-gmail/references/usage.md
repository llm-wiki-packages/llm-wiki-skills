# channel-gmail — usage

Invoked `/channel-gmail ticket=<id> stage=<harvest|process>`. The step is the
`stage` that `tickets open <id>` answers. One invocation serves one mailbox
(`options.mailbox`) and one day directory; it takes no other argument.

## Script

`scripts/write_items.py`, run as `llm-wiki-ops run ops/skills/channel-gmail/scripts/write_items.py <arm> <capture_dir> --ticket <id> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| arm | step | further argv |
| :--- | :--- | :--- |
| `since` | harvest, first | `[--lookback-days N]` (default 7); prints `since`, `since_day`, `first_pull`, `mailbox`, `cursor_ignored` |
| `write` | harvest, last | `[--from FILE] [--cap N] [--partial WHY] [--exclude-label L]… [--exclude-sender ADDR\|@domain]…`; or, for a pull that read nothing, `--failed WHY --missing HOST URL denied\|timeout\|auth\|error` |
| `ledger` | process | `[--from FILE] [--partial WHY]` |

`--from` defaults to `pull.json` (`write`) and `lines.json` (`ledger`) in the
capture directory. `--cap` defaults to 200. Give `write` one of the pull form
or `--failed`, never both. `-h` after an arm lists the rest.

## Knobs

- `watch.inputs.mailbox` (required) lands as `options.mailbox`; the job's slug
  keys the cursor, the `_raw` slice and the ledger.
- The mechanical filters are the flags on `write` and `since`; this wiki's
  values are SKILL.md "Mechanical filters".
- `process.exclude_rules` feeds the junk rules (SKILL.md, process).
- `requires.file` is `required`: a per-mailbox credential binding the unit
  never reads (SKILL.md "The binding").
