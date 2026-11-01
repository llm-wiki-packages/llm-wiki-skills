# channel-blackboard — usage

Invoked `/channel-blackboard <command>` in a session at the wiki root. The
script runs as `{{@brain-cli-ops}} run ops/skills/channel-blackboard/scripts/bb.py <command> …`;
`-h` after any command prints its own help.

## Commands

| command | argv |
| :--- | :--- |
| `login` | `<base_url> (--profile DIR \| --credential NAME) [--chrome] [--timeout-min 15]` |
| `whoami` | `(--profile DIR \| --credential NAME) [--chrome] [--headed]` |
| `courses` | the same |
| `get` | `<api-path> [--all]` and the same; `v1/...` is under `/learn/api/public`, a leading `/` is a site path |
| `harvest` | `<course id> --out DIR [--no-files]` and the same |

`--credential NAME` reads the profile directory off `{{@brain-cli-ops}}
credentials info NAME` (a `kind=dir` credential). Exit 0 ok; 2 not signed in
or the session expired; 3 usage or an unreadable profile; 4 an API error
that is not auth.

## What `harvest` writes

| file | what |
| :--- | :--- |
| `course.json`, `contents.json` | the course; every content item, flat, with `path`, `handler`, `syllabus` |
| `bodies/<itemId>.html` | each item's HTML body |
| `files/<item path>/…` | attachments, files the bodies embed or link, and the pages those iframe |
| `files/_announcements/`, `files/_discussions/<board>/` | files those embed |
| `files/_submissions/<column>/` | the student's own submitted files |
| `announcements.json`, `calendar.json` | as the API answers them |
| `discussions.json`, `discussions/<id>.json` | the boards, and every post the student can see |
| `gradebook-columns.json`, `my-grades.json` | assignments with due dates and points; the student's grades and feedback |
| `attempts.json`, `attempts/<id>.json` | the student's attempts; the detail carries rubric scores and file references |
| `external.json` | every off-site link, `video: true` for a video host; not fetched |
| `files.json`, `errors.json`, `summary.json` | what landed, what failed, the totals |
