# channel-frameio — usage

Invoked `/channel-frameio ticket=<id>`; the runner adds `stage=<harvest|process>` to the
slice prompt, but the step followed is the `stage` that `tickets open <id>` answers.
No other argument. One harvest ticket captures a whole share; one process ticket writes one leaf.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-frameio/scripts/<script> …`.
`<capture_dir>` is the ticket's own, wiki-relative, verbatim.

| script | step | argv |
| :--- | :--- | :--- |
| `enumerate_tree.py` | harvest | `<target> --out <capture_dir>/tree.json` |
| `harvest_share.py` | harvest | `<capture_dir> --ticket <id> [--title-strip S] [--author NAME] [--group NAME] [--group-type KIND] [--plan-only] [--retry-failed]`; bounded, so re-run while its summary says `"stop": "budget"` |
| `frameio_doc_note.py` | process | `. --capture-dir <capture_dir> --dest <dest> --ticket <id> [--skip REASON]`; the `.` is the wiki root |

`harvest_share.py` calls `capture_job.py`, which calls `capture_asset.py`;
`capture_record.py` is imported by `capture_job.py` and `frameio_doc_note.py`.
None of the three is run by hand. `frameio_doc_note.py` also takes `--item`,
`--name`, `--path`, `--crumb-skip`, `--title-strip`, `--author`, `--group`,
`--group-type`, only for a capture harvest did not record in `meta.json`.

## Knobs

- No `watch.inputs`. `harvest.scope` must be `domain` (the shipped default).
  `harvest.assets` is `download` by default; `harvest.exclude_urls` and
  `known[]` filter the plan. `harvest.access`, `min_date` and `dest` are not
  consulted at harvest (SKILL.md "Read the job").
- `process.exclude_rules` is applied first at process; `process.bundle_media`
  (off unless true) puts a video leaf's media under `<dest>/assets/`.
- `yt-dlp` must be on PATH. The unit holds no credential.
