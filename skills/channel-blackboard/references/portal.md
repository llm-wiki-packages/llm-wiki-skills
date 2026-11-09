# channel-blackboard — a portal job

## What a portal job is

One job that follows every course a student is enrolled in, instead of one
job per course. Its target is the site's courses page,
`https://<host>/ultra/course`, and its `dest` is the folder above the courses
(for example `sources/courses/<school>`). Each pull lists the enrollments,
decides which courses are due, and pulls them under one harvest ticket.

```sh
{{@brain-cli-ops}} jobs add https://<host>/ultra/course skill=channel-blackboard dest=sources/courses/<school> every=1d harvest.budget=6h
```

Set `harvest.budget` high enough for a first pull of every course: the first
pull downloads every file.

## Where each course lands

Each course gets its own folder under the job's `dest`, named by its short
code: `PSY2301` for `PSY2301-21.01.01-2B27-S3`, a subject of 2 to 5
letters and a number of 3 to 5 digits at the start of the course id. A
course with no such code is named by its course id, made safe for a folder
name. Two courses that would share a folder get a numbered suffix (`-2`). A
course's folder never changes once given, even when the course is renamed:
`items/portal.json` in the capture remembers it.

Inside the folder the layout is the one-course layout
(`references/layout.md`): the course root, one folder per module, and the
announcements and discussions folders.

## Which courses are pulled

| Status | When | Pulled |
| :--- | :--- | :--- |
| `active` | Running, or the course states no dates | Every pull |
| `dormant` | Active, but nothing changed in 42 days | Once a week |
| `upcoming` | Its start date is in the future | No |
| `finished` | 21 days past its end date | Until one pull with no failures, then never |
| `closed` | The student's membership or the course is unavailable | No |
| `organization` | A Blackboard organization, not a course | No |

A course with no dates counts as `active`: pulling too much is the mistake
that loses nothing. The pull that first finds a course `finished` or
`dormant` sets `current: false` on its root; a course that is running again
gets `current: true`. A person's later edit of the root stands.

## Options

- `options.subject_tags`: tags by course-code prefix, comma-separated
  `PREFIX=tag` pairs (`PSY=psychology,LSS=study-skills`). A new course's
  root gets its tags at creation and lends them to every page below
  (`ops.lends`). A course with no matching prefix gets none, and the
  harvest's reason names it.
- `options.skip_courses`: course ids or codes to leave out, comma-separated.
- `options.discover_only=true`: list and classify the enrollments and fetch
  nothing. The answer is `portal-report.json` in the capture.

Every one-course option (`discussions`, `files`, `timezone`, `layout`, …)
applies to every course.

## Files

A file already downloaded is reused, not fetched again, unless the item
that holds it changed (`modified`). A file the site answers with 403, 404 or
410 is gone for this student: it is recorded in the course's
`harvest/<folder>/gone.json`, named in the harvest's reason, and not fetched
again while its item is unchanged. A gone file never makes the harvest
`partial`, because no re-run can fetch it. A busy site (429, 5xx) or a
dropped connection is asked again twice before the call counts as failed.
