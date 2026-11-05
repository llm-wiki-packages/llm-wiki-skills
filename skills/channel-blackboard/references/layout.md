# channel-blackboard — course layout, fields and weekly releases

How a followed course's pages are laid out under the job's `dest`, which
frontmatter each carries, how the course index reads, and what a pull does
as modules are released week by week. Every choice is a job option, so two
courses can differ; a new job takes the unit's `watch.defaults.options`.

## The layout options are job options, read by both stages.

| option | words (first is the default a new job takes) | what |
| :--- | :--- | :--- |
| `options.layout` | `modules`, `flat` | `modules`: a folder per top-level lesson or folder; `flat`: one folder, module-ordered names |
| `options.prefix` | `position`, `none` | the outline position as a zero-padded filename prefix, or none |
| `options.announcements_dir` | `announcements`, any one folder name, `alongside` | where announcement pages go |
| `options.discussions_dir` | `discussions`, any one folder name, `alongside` | where discussion board pages go |
| `options.backfill` | `changed`, `none`, `all` | which written pages a pull re-renders (below) |
| `options.depth` | `1` | top-level modules; a deeper item is numbered `03.02` in its module's folder |

A job added before 0.3.0 has no `layout`, and keeps the layout its pages
already have (`legacy`: one folder, a page per title): no verb moves a
`sources/` page, so a new layout on an old job would leave two layouts in
one folder. Any other word is a `failed` harvest naming it.

The course folder is the job's `dest`, chosen at `jobs add`: the slug
(`sources/courses/<slug>`, the default), the course code
(`dest=sources/courses/ABC1301`) or a term above it
(`dest=sources/courses/2026-fall/<slug>`). The term is a field either way.

## With `layout=modules` a course reads in its own order.

```
sources/courses/<slug>/
  README.md                       course root: the course's keys
  00 Course overview.md           the course index, re-rendered each pull
  01 Start Here/README.md         module root: the module's keys
  01 Start Here/01 Quality Matters.md
  04 Unit IV/README.md
  04 Unit IV/01 Unit IV Study Guide.md
  04 Unit IV/01 Unit IV Study Guide — UnitIV.pdf.md   a file sorts after the item carrying it
  04 Unit IV/02 Unit IV Journal.md
  announcements/2026-10-24 Week 5 approaching fast.md
  discussions/Unit I Discussion Board.md
```

- The prefix is the outline position, one-based: the module's, then the
  item's within it. A folder whose one child is a document (Ultra's
  `ultraDocumentBody`, a `Part 1.` folder) is that document's place.
- The filename drops the course code; the page's `title` keeps it
  (`PSY 2301 — Unit IV Journal`), and every link the unit writes names the
  page's path, so two courses' `01 Study Guide` never collide.
- `flat`: `04.02 Unit IV — Unit IV Journal.md`, all in `dest`.
- A place is decided once, the pull that first sees the item, and kept in
  `items/placement.json` under the job's `_raw`: an instructor inserting an
  item renumbers no existing page, though two pages may then share a
  prefix. The `position` field always says where the item sits now.
- A module's pages go to the folder whose `README.md` carries the module's
  `module_id`, wherever that is: a person may rename a module folder.

## Each root lends its keys to the pages below it.

The course root (`README.md` in `dest`) is made by the first pull, once,
and is the person's after: `root`, `current`, `term` (the course's dates,
never a name derived from them), `term_start`, `term_end`, `course`
(`PSY 2301`), `course_title`, `course_id`, `section`, `group`,
`group_type: course`, `channel: blackboard`, `source_host`, `course_url`, and
the job record's own `root.<key>` answers over them. `filter=group:PSY 2301`
scopes a search to the course. `areas` and `tags` are the job's `meta`
(`jobs add … meta.tags=course/psy2301`), which the CLI stamps on every page.

A module root (`modules` only) is made once when its module first has a
page, recorded in `modules-made.json` in the course capture: `module`,
`module_order` (`Unit IV` reads 4; `Module 3-`, `Part 2.` and `Week 12`
too), `module_position`, `module_kind` (lesson or folder), `released` (the
pull that first saw its items) and `module_id`. A root a person deleted is
never made again.

Each page carries its own: `kind` (`assignment`, `study-guide`,
`document`, `file`, `video`, `announcement`, `discussion`, `overview`),
`outline_path`, `position`, `bb_id`, `due` (to the minute, in the job's
`timezone`, with its offset), `points`, and on a file or video `part_of`, a
link to the item that carries it. `module` is a page field only where there
is no module root (`flat`, `legacy`). A grade, its status and feedback are
never fields: the overview's gradebook dates them by the pull.

## The course overview is the course index.

`00 Course overview` is pipeline-owned and re-rendered whenever the course
changes: `## Added this week` (pages a pull first saw in the last seven
days, the first pull's own excepted), `## Outline` (every module and item in
course order, each linked to its page, with due dates and points, and each
file and video under its item), `## Gradebook`, `## Calendar`,
`## Off-site links`, and `## Removed from the course`. A course link that
shares a discussion board's title links the board. Module roots link the
overview; they hold no list of their own, which a made-once page would let
go stale.

## A weekly release is a new module folder, and an edit re-renders its page.

- A lesson not yet released lists no children and makes no folder. The pull
  that first sees its items places them, and the course capture makes its
  folder root with `released`.
- `backfill=changed` (default): every new or edited item is posted again,
  in any module.
- `backfill=none`: a written page in a module whose last due date is seven
  days past is no longer re-rendered; a new item there still is, and an
  edit held back is posted if the module thaws (a due date moved). It saves
  page writes, not fetches: `bb.py` still pulls the whole course.
- `backfill=all`: every page re-renders every pull, as a refresh does.
- An item or board two whole pulls in a row have not listed is posted once
  more: process writes `removed: <day>` on its page and nothing else, and
  the overview lists it under Removed. Nothing is judged from a listing
  that failed, a lesson that lists no children, an item still in the
  outline with nothing left to render, or a board `discussions=skip` stopped
  fetching; an announcement leaves at the end of its display window, and is
  never judged. Every later write of a listed item clears `removed`.
  `Archive` stays the person's box: an archived page takes no write, so a
  returning item could not be brought back.
- A page a person moved is left alone, as before.

## Pages made by hand do not join a job's layout.

`bbnotes notes --layout modules` writes the same folders and names by
hand, but carries no `resource`, so a later job on that course writes a
page of its own beside each. Process names a folder beside `dest` that
differs from it only by case (`ABC1301` beside `abc1301`): one directory on
a case-insensitive disk, two to git.
