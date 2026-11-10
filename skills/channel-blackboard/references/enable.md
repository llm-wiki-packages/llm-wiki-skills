# channel-blackboard — after enabling

1. Make the credential, naming the institution's Blackboard host:
   `{{@brain-cli-ops}} credentials set blackboard kind=dir login=browser host=<host>`.
   A second institution is a second credential under its own name.
2. Sign in, attended: `{{@brain-cli-ops}} credentials login blackboard`. The
   credential store never syncs, so every machine that harvests signs in once.
3. Check it: `/channel-blackboard courses` lists the memberships.
4. **Choose the layout, once for the wiki.** Ask the person, offering the
   recommendation first:
   - layout: a folder per module, files named in course order
     (`modules`, recommended) or one folder (`flat`);
   - filename prefix: the outline position (`position`, recommended) or none;
   - announcements and discussion boards: their own folders (recommended),
     or `alongside` the modules;
   - backfill: re-render what changed anywhere (`changed`, recommended),
     leave a module alone a week after its last due date (`none`), or
     re-render everything each pull (`all`);
   - the course folder: the job slug (recommended), the course code, or a
     term folder above it — this is `dest=` on each `jobs add`
     (`dest=sources/courses/ABC1301`, `dest=sources/courses/2026-fall/<slug>`).

   The unit's `watch.defaults.options` hold the recommendations
   (`layout=modules`, `prefix=position`, `backfill=changed`,
   `announcements_dir=announcements`, `discussions_dir=discussions`). Write
   any other answer there, in the installed copy's `manifest.json`, so every
   later `jobs add` on every machine takes it; a layout also goes in
   `watch.inputs.layout.default`, the answer `jobs add` offers, which must
   agree with it. One course that differs takes
   `options.<key>=<word>` on its own `jobs add`. Tell the person what was
   chosen. A job's options are fixed at `jobs add`, and no verb moves a page
   once written: a change applies to jobs added after it, and to a job edited
   (`{{@brain-cli-ops}} jobs edit <slug> options.layout=modules`) before its
   first pull. What each word does:
   `{{@brain-cli-ops}} reference channel-blackboard/references/layout.md`.
5. Follow a course, one job each. The target is the course's url as the
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
   does not know. `options.current=true|false` (default `true`) says whether
   the course is one you're taking now; it is written once, onto the course
   root below.
6. **Map the profile to the job**, on each machine that harvests:
   `{{@brain-cli-ops}} credentials bind job <course> dir=blackboard`. The
   slice is granted that directory read-write, and the ticket names it as
   `credential_dir`. The manifest declares the slot `"required"`, so a
   machine that maps nothing claims none of the job's harvests. Bind the
   job, not the skill: a skill's `dir` is handed to every job of the skill,
   unattended.
7. Videos with no captions are spoken by this machine's transcribe engine
   (`{{@brain-cli-ops}} config get transcribe.engine`; `/{{@brain-plugin}}:join`
   settles one). With none declared, their transcribe tickets wait and their
   pages go out without a transcript until one runs.

## What a run leaves

| where | what |
| :--- | :--- |
| `_raw/<slug>/…/harvest/` | `bb.py harvest`'s output, whole (`usage.md`'s table) |
| `_raw/<slug>/…/items/<kind>-<id>/` | one capture per page: `capture.json`, and the file, video or `record.json` it renders from |
| `_raw/<slug>/…/items/placement.json` | where each page was first placed, each module's folder, and what left the course |
| `sources/courses/<slug>/README.md` | the course root, made by the first pull and never rewritten — nor made again once deleted (`root-made.json` in the course capture, `_raw/<slug>/…/items/course/`, records it): `ops.root: true`, `current`, `term`, the course's code, title, ids, dates and host, `group`, and an `abstract`. Every page a pull makes in the folder copies them (`ops.lends` names which); edit it (`page edit <path> current=false`) when the course ends, and `page root apply <path> --force` updates the pages already there |
| `sources/courses/<slug>/NN <module>/README.md` | each released module's root, made once the same way (`modules-made.json`): `module`, `module_order`, `released` and the rest |
| `sources/courses/<slug>/` | one page per capture, each with an `abstract` and its fields (`kind`, `position`, `due`…): `00 Course overview` (the course index), each content item, each pdf, slide deck, Word file or html page, each video, each announcement, each discussion board (in parts past 60 KB) |

A harvest posts only the captures that are new or changed since the last
pull, so a daily job re-renders the boards that got posts and the items an
instructor edited, and nothing else.
