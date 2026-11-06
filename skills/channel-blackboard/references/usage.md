# channel-blackboard — usage

Invoked `/channel-blackboard <command>` in a session at the wiki root. The
script runs as `{{@brain-cli-ops}} run ops/skills/channel-blackboard/scripts/bb.py <command> …`;
`-h` after any command prints its own help.

## Commands

| command | argv |
| :--- | :--- |
| `bb.py login` | `<base_url> (--profile DIR \| --credential NAME) [--chrome] [--timeout-min 15]` |
| `bb.py whoami` | `(--profile DIR \| --credential NAME) [--chrome] [--headed]` |
| `bb.py courses` | the same |
| `bb.py get` | `<api-path> [--all]` and the same; `v1/...` is under `/learn/api/public`, a leading `/` is a site path |
| `bb.py harvest` | `<course id> --out DIR [--no-files] [--no-discussions]` and the same |

Every command above also takes `--site <base url>`, over the profile's
`bb-site.json`; the harvest stage passes the job target's.

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

## `bbnotes.py`

`{{@brain-cli-ops}} run ops/skills/channel-blackboard/scripts/bbnotes.py <command> …`.
No network and no credential: it reads a harvest directory.

| command | argv | what |
| :--- | :--- | :--- |
| `bbnotes.py split` | `<harvest dir> --out DIR [--tz ZONE] [--layout legacy\|modules\|flat]` | one capture dir per page under `DIR`, each with `capture.json` (its `place` and `fields`), and `DIR/placement.json` |
| `bbnotes.py render` | `<capture dir> [--out FILE] [--tz ZONE]` | that capture's page(s) as JSON: `title`, `type`, `published`, `abstract`, `body`, and `problem` where its text could not be had |
| `bbnotes.py notes` | `<harvest dir> --out DIR [--items DIR] [--tz ZONE] [--layout legacy\|modules\|flat]` | `split` and `render` together: one Markdown note per page in `DIR`, at its place under `--layout` |

The captures, by `kind` in `capture.json`:

| kind | page type | renders from |
| :--- | :--- | :--- |
| `course` | `document` | the course index: what was added this week, the outline with each page linked in course order, due dates and points, the gradebook (the student's grades and feedback), the calendar, off-site links, what left the course |
| `item` | `document` | one content item with a body, instructions or a grade column; a bare link or folder is a line of the outline instead |
| `file` | `document` | a pdf (pypdf, layout mode), slide deck (slide text and speaker notes), Word file or html page an item carries |
| `video` | `video` | the transcript beside the media: the transcribe stage's `.transcript.webvtt`, else an English caption track |
| `announcement` | `note` | one announcement |
| `discussion` | `note` | one board's prompt and every published post, threaded by reply; parts past 60 KB |

`abstract` is one line of at most 600 characters, built from the capture's
facts with no model: the kind and course, a due date in `--tz` and points,
a video's length by its transcript, and the text's first heading and
sentence.

`published` is the day the item was last modified, an announcement's last
edit, or a board's latest post. Titles are settled across the course: two
items called "Introduction" are two pages, each qualified by the folder above
it ("Introduction (Week 2)"), or by its id's tail where they share a folder:
never by a count, so a new item never renames another. A discussion's later
parts are their own resources, `<item>#part-<n>`. Dates read in `--tz`.

`render` links a page by its place, else its title; `process.py` passes each
page's path instead. Where a page goes and its fields:
`{{@brain-cli-ops}} reference channel-blackboard/references/layout.md`.
