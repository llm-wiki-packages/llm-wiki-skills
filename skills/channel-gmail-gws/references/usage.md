# channel-gmail-gws — usage

The pipeline: `/channel-gmail-gws ticket=<id>`, started by the runner, never
typed. The harvest is a script stage; the process step is a session that
follows the `stage` `tickets open <id>` answers. One invocation serves one
mailbox (`options.mailbox`) and one day directory.

The attended modes: `/channel-gmail-gws <mode> [flags]`, typed by the
operator — `triage`, `digest`, `reply`, `followup`, `clean`, `setup`. Never
unattended: `reply`, `followup` and `clean --apply` write to the mailbox.

## Scripts

Each runs as `{{@brain-cli-ops}} run ops/skills/channel-gmail-gws/scripts/<script> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| script | step | argv |
| :--- | :--- | :--- |
| `harvest.py` | harvest, the whole stage | `ticket=<id>`, as the runner starts it |
| `write_items.py ledger` | process, last | `<capture_dir> --ticket <id> [--from lines.json] [--partial WHY]` |
| `write_items.py since` | by hand: where the next pull starts | `<capture_dir> --ticket <id> [--lookback-days N]` |
| `write_items.py write` | harvest, called by `harvest.py` | `<capture_dir> --ticket <id> [--from pull.json] [--cap N] [--partial WHY] [--exclude-label L]… [--exclude-sender ADDR]…`, or `--failed WHY --missing HOST URL WHY` |
| `gmail_pull.py` | attended, pull | `--out FILE [--query Q] [--max N] [--bodies] [--mailbox ADDR] [--config-dir DIR]` |
| `gmail_draft.py` | attended, a draft | `--reply-to MSG_ID [--all]` or `--to ADDR --subject S [--cc ADDR]`; `[--body-file F] [--config-dir DIR] [--dry-run]` |
| `gmail_apply.py` | attended, label/archive/read/star | `--from verdicts.json --writes LIST [--apply] [--create-labels] [--config-dir DIR]` |

`gwscli.py` is the scripts' shared gws caller; nothing runs it directly.

## Knobs

- `options.mailbox` (required) — the address the job's login must be signed into.
- `options.lookback_days` (7), `options.cap` (200), `options.exclude_labels`
  (`CATEGORY_PROMOTIONS,CATEGORY_SOCIAL,SPAM,TRASH`), `options.exclude_senders`
  (none) — the harvest's mechanical filters, per job.
- The ticket's `min_date` clamps where a pull starts.
- `process.exclude_rules` adds junk rules to the profile's.
- `requires.credentials.dir` is `required`: the job's read-only gws login directory,
  bound per machine (`references/enable.md`).
- The profile and any wiki playbook: this unit's policy overlay.
