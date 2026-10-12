# channel-youtube — usage

Invoked `/channel-youtube ticket=<id> stage=<harvest|process>`. The step is the
`stage` that `tickets open <id>` answers; it takes no other argument. Harvest
is a script stage and runs no session; process is the session's. Single videos
are the proven shape.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-youtube/scripts/<script> …`.

| script | step | argv |
| :--- | :--- | :--- |
| `capture_video.py` | harvest | `ticket=<id>`, as the runner starts it; the whole worker, posting its own update |
| `youtube_note.py` | process | `. --capture-dir <capture_dir> --dest <dest> --ticket <id> [--format-transcript PATH]`; the `.` is the wiki root, `<capture_dir>` the ticket's own, wiki-relative; `--record` is the harvest arm `capture_video.py` runs |
| `export_cookies.py` | harvest | `<profile_dir> <out_file>`; run by `capture_video.py` under `browser_python`, not by hand |

## Knobs

- No `watch.inputs`. `harvest.assets` is `reference` by default: only metadata
  and captions are fetched. `harvest.scope` defaults to `page`.
  `harvest.refresh` is off by default.
- `process.exclude_rules`, `options` and `min_date` are applied first at
  process.
- `requires.dir` is `optional`: a `login: browser` credential adds a cookie jar
  for private, age-restricted and members-only videos (SKILL.md "Auth").
  `yt-dlp` must be on PATH.
