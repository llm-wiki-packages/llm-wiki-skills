# channel-youtube — usage

Harvest is a script stage (`stages.harvest.script`): the runner starts
`capture_video.py ticket=<id>` with no session and no slash invocation. Only
process is invoked, as `/channel-youtube ticket=<id> stage=process`, and takes
no other argument. Single videos are the proven shape.

## Scripts

Each runs as `llm-wiki-ops run ops/skills/channel-youtube/scripts/<script> …`.

| script | step | argv |
| :--- | :--- | :--- |
| `capture_video.py` | harvest | `ticket=<id>`, as the runner starts it; the whole worker, posting its own update |
| `youtube_note.py` | process | `. --capture-dir <capture_dir> --dest <dest> --ticket <id> [--format-transcript PATH]`; the `.` is the wiki root, `<capture_dir>` the ticket's own, wiki-relative; `--record` is the harvest arm `capture_video.py` runs |
| `export_cookies.py` | harvest | `<profile_dir> <out_file>`; run by `capture_video.py` under `browser_python`, not by hand |

## Knobs

- No `watch.inputs`. The harvest script reads `item`, `capture_dir`, `known[]`,
  `refresh`, `credential_dir` and `browser_python` off the ticket.
- `process.exclude_rules`, `options` and `min_date` are applied first at
  process; `process.embeds` (default on) controls the embed in the page body.
- `requires.dir` is `optional`: a `login: browser` credential adds a cookie jar
  for private, age-restricted and members-only videos (SKILL.md "Auth").
  `yt-dlp` must be on PATH.
