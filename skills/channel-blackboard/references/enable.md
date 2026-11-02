# channel-blackboard — after enabling

1. Make the credential, naming the institution's Blackboard host:
   `{{@brain-cli-ops}} credentials set blackboard kind=dir login=browser host=<host>`.
   A second institution is a second credential under its own name.
2. Sign in, attended: `/channel-blackboard login https://<host>`. The
   credential store never syncs, so every machine that harvests signs in once.
3. Check it: `/channel-blackboard courses` lists the memberships.
4. Follow a course, one job each. The target is the course's url as the
   browser shows it, and its host is the site the job reaches:
   `{{@brain-cli-ops}} jobs add 'https://<host>/ultra/courses/<id>/outline'
   slug=<course> skill=channel-blackboard description="<course name>"
   options.timezone=<IANA zone>`. The manifest supplies `every=1d`, a
   `dest` of `sources/courses/<slug>` and a `transcribe` section
   (`when: if-no-captions`). Without `options.timezone` a due date reads in
   UTC, which puts a midnight deadline on the next day. `options.files=skip`
   fetches no attachment, pdf or video: the pages then carry the course's
   text alone. `options.discussions=skip` fetches no discussion board: a
   board's page names every classmate who posted and holds their posts, and
   `sources/` is committed and pushed to the wiki's remote with the rest.
   Any other word for either is a `failed` harvest, as is a zone this machine
   does not know.
   text alone. `options.current=true|false` (default `true`) says whether
   the course is one you're taking now; it is written once, onto the course
   root below.
5. **Map the profile to the job**, on each machine that harvests:
   `{{@brain-cli-ops}} credentials bind job <course> dir=blackboard`. The
   slice is granted that directory read-write, and the ticket names it as
   `credential_dir`. The manifest declares the slot `"required"`, so a
   machine that maps nothing claims none of the job's harvests. Bind the
   job, not the skill: a skill's `dir` is handed to every job of the skill,
   unattended.
6. Videos with no captions are spoken by this machine's transcribe engine
   (`{{@brain-cli-ops}} config get transcribe.engine`; `/{{@brain-plugin}}:join`
   settles one). With none declared, their transcribe tickets wait and their
   pages go out without a transcript until one runs.

## What a run leaves

| where | what |
| :--- | :--- |
| `_raw/<slug>/…/harvest/` | `bb.py harvest`'s output, whole (`usage.md`'s table) |
| `_raw/<slug>/…/items/<kind>-<id>/` | one capture per page: `capture.json`, and the file, video or `record.json` it renders from |
| `sources/courses/<slug>/README.md` | the course root, made by the first pull and never rewritten: `root: true`, `current`, `term`, and an `abstract`. Every page in the folder inherits `current` and `term`; edit it (`page edit <path> current=false`) when the course ends |
| `sources/courses/<slug>/` | one page per capture, each with an `abstract`: the course overview, each content item, each pdf, slide deck, Word file or html page, each video, each announcement, each discussion board (in parts past 60 KB) |

A harvest posts only the captures that are new or changed since the last
pull, so a daily job re-renders the boards that got posts and the items an
instructor edited, and nothing else.
