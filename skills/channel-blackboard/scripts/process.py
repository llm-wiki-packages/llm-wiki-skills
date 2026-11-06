#!/usr/bin/env python3
"""The Blackboard process stage: one capture into its page(s) under the job's dest. No model session, no network.

  llm-wiki-ops run ops/skills/channel-blackboard/scripts/process.py ticket=<id>

Reads the ticket through `tickets open`; its `capture_dir` is one item
directory `harvest.py` posted. `bbnotes.render` makes the page: a content
item's text and due date, a pdf, slide deck or Word file's text, a video's
transcript, an announcement, a discussion board's posts (in parts past
60 KB), or the course overview. Each page is written through `page create`
where no page holds its `resource`, or `page edit` of the page `known[]`
names for it. A page a person moved (`reason: moved`) or holds (`held[]`) is
left alone: `ok`, nothing written. A page at the title's path that is another
item's, or no item's, is never written over: `partial`, naming it. A
discussion's later parts are their own resources, `<item>#part-<n>`.
Every page carries an `abstract` built from the capture's facts, and the
capture's `fields` (`kind`, `outline_path`, `position`, `bb_id`, `due`,
`points`, and `part_of` linking a file or video to the item that carries
it).

A new page goes where the capture's `place` says under `dest` (the job's
`layout` option, `bbnotes.layout_of`): its filename is the place's stem
(`01 Unit IV Study Guide`), and a second `page edit` gives it the page's
whole title. A module's pages go to the folder whose `README.md` names the
module's `module_id`, where one exists, so a renamed folder or a second
harvesting machine's plan never splits a module. A module with no root
there goes where most of its written pages now sit, so a person who moves a
module's pages or flattens its folder is followed. Every link a page makes
names the target's path: `known[]`'s where it was written, else its place.

The course overview's capture also makes the course's bundle root, once:
`README.md` in `dest` with `root: true`, `current` (the job's `current`
option: true, false, yes or no; default true), `term`, `term_start`,
`term_end`, `course`, `course_title`, `course_id`, `section`, `group`,
`group_type: course`, `channel: blackboard`, `source_host` and `course_url`,
and the job record's own `root` keys over them, which every page below
inherits. A root already there (`page ls filter=prop:root`) is left
alone, and `root-made.json` in the course capture records that the question
was settled, so a root a person deleted is never made again. Each released
module's folder root (`module`, `module_order`, `module_position`,
`module_kind`, `released`, `module_id`) is made the same way, once, recorded in
`modules-made.json`. A folder beside `dest` that differs from it only by
case is named in the reason.

A capture stamped `removed` (an item the course stopped listing) edits only
`removed: <day>` onto its page; the item's return clears it.

`ok` with the pages in `written.json`; `partial` where a page went out
without its text (a scanned pdf, a video no transcript reached yet: the
transcribe stage writes one where the job has a `transcribe` section, and the
next pull re-renders the page). The job's `timezone` option is the zone due
dates read in.

Stdlib only, no PEP 723 block: a script stage runs under the ops interpreter,
whose `pypdf` reads the pdfs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bbnotes  # noqa: E402
from door import open_ticket, ops_json, post_update  # noqa: E402

WRITTEN = "written.json"
# The course's bundle root in the job's dest (the note format's Bundle roots): `root: true`, and the keys its pages inherit.
ROOT = "README.md"
# In the course capture's own directory: the root was made (or found) once, so a pull never makes it again.
ROOT_MADE = "root-made.json"
# Beside it: the modules whose folder root was made (or found), by module id.
MODULES_MADE = "modules-made.json"


RESOURCE_LINE = re.compile(r"^resource:\s*['\"]?(.*?)['\"]?\s*$", re.MULTILINE)


def resource_of(path: Path) -> str | None:
    """The `resource` a page's own frontmatter names, or None."""
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            head = f.read(16384)
    except OSError:
        return None
    if not head.startswith("---"):
        return None
    found = RESOURCE_LINE.search(head.split("\n---", 1)[0])
    return found.group(1) if found and found.group(1) else None


MODULE_ID = re.compile(r"^module_id:\s*['\"]?(_\d+_\d+)['\"]?\s*$", re.MULTILINE)


def module_folders(dest: str) -> dict[str, str]:
    """Each module folder under `dest` by the module id its root's `module_id` names: where a module's pages go, whatever this
    machine's ledger planned, so a second machine, or a folder a person renamed, keeps one folder per module."""
    out = {}
    for readme in sorted(Path(dest).glob("*/README.md")) if Path(dest).is_dir() else []:
        try:
            head = readme.read_text(encoding="utf-8", errors="replace")[:8192]
        except OSError:
            continue
        found = MODULE_ID.search(head.split("\n---", 1)[0]) if head.startswith("---") else None
        if found:
            out.setdefault(found.group(1), readme.parent.name)
    return out


def module_homes(cap: dict, dest: str, known: dict[str, dict], ledger: dict) -> dict[str, str]:
    """Each planned module's folder by where most of its written pages sit under `dest` now (`""`: `dest` itself): a person
    who moved a module's pages, or flattened its folder and deleted its root, sees the module's next item join them, not
    its first folder made again. A page moved out of `dest` is the person's, and casts no vote."""
    course, base = cap["item"].rsplit("/", 1)[0], f"{dest.rstrip('/')}/"
    pages, out = ledger.get("pages") or {}, {}
    for mid, row in (ledger.get("modules") or {}).items():
        prefix = f"{row.get('folder') or ''}/"
        votes: dict[str, int] = {}
        for key, page in pages.items():
            if prefix == "/" or not str(page.get("place") or "").startswith(prefix):
                continue
            hit = known.get(f"{course}/{key}") or {}
            path = hit.get("path") or ""
            if hit.get("reason") == "moved" or not path.startswith(base):
                continue
            folder = path[len(base):].rpartition("/")[0]
            votes[folder] = votes.get(folder, 0) + 1
        if votes:
            out[mid] = max(sorted(votes), key=votes.__getitem__)
    return out


def placed(place: str | None, module: str | None, folders: dict[str, str]) -> str | None:
    """A planned place with its module folder as `dest` holds it (`""`: a module flattened into `dest`)."""
    if place and module and module in folders and "/" in place:
        stem = place.split("/", 1)[1]
        return f"{folders[module]}/{stem}" if folders[module] else stem
    return place


def link_paths(cap: dict, dest: str, known: dict[str, dict], folders: dict[str, str]) -> dict[str, str]:
    """The target of every link the capture's page makes: the page's path, by `known[]` where it was written, else where it goes."""
    course = cap["item"].rsplit("/", 1)[0]
    rows = {**(cap.get("links") or {}), bbnotes.cap_key(cap): {"title": cap.get("title"), "place": cap.get("place"), "module": cap.get("module")}}
    out = {}
    for key, row in rows.items():
        path = (known.get(f"{course}/{key}") or {}).get("path")
        where = placed(row.get("place"), row.get("module"), folders)
        out[key] = path.removesuffix(".md") if path else f"{dest.rstrip('/')}/{where or row.get('title') or key}"
    # A discussion's later parts: where each was written, else beside where its first part goes (`#base`), or in `dest` (`#dir`).
    own = bbnotes.cap_key(cap)
    for res, row in known.items():
        if res.startswith(f"{course}/{own}#part-") and row.get("path"):
            out[f"{own}#part-{res.rsplit('#part-', 1)[1]}"] = row["path"].removesuffix(".md")
    where = placed(cap.get("place"), cap.get("module"), folders)
    if where:
        out[f"{own}#base"] = f"{dest.rstrip('/')}/{where}"
    out[f"{own}#dir"] = dest.rstrip("/")
    return out


def write_page(page: dict, resource: str, dest: str, known_path: str | None, place: str | None = None,
               fields: dict | None = None) -> tuple[str | None, str | None, bool]:
    """`(path, None, False)` written; `(None, why, True)` a page that is not this item's stood at the path; `(None, why, False)` refused.
    `place` is where a new page goes under `dest` (`<folder>/<stem>`); its filename is the stem, its `title` the page's."""
    pairs = [f"type={page['type']}", f"resource={resource}", "extracted=true"]
    # An edit names the title too: an item the instructor renamed keeps its filename (its place) and takes its new title.
    titled = [f"title={page['title']}"]
    if page.get("abstract"):
        pairs.append(f"abstract={page['abstract']}")
    if page.get("published"):
        pairs.append(f"published={page['published']}")
    # A listed item is in the course: an edit clears a `removed` an earlier pull wrote, on whichever machine (a no-op where absent).
    clears = [f"{k}=" for k, v in (fields or {}).items() if v in (None, "")] + ["removed="]
    pairs += [f"{k}={v}" for k, v in (fields or {}).items() if v not in (None, "")]
    path = known_path or f"{dest.rstrip('/')}/{place or page['title']}.md"
    if known_path:
        rc, answer = ops_json("page", "edit", path, *pairs, *titled, *clears, "--stdin", stdin=page["body"])
    elif Path(path).is_file():
        # Not this item's page by `known[]`: edit it only where its own frontmatter says it is.
        other = resource_of(Path(path))
        if other != resource:
            return None, f"{path} holds {'another item, ' + other if other else 'a page no item wrote'}: not written over", True
        rc, answer = ops_json("page", "edit", path, *pairs, *titled, *clears, "--stdin", stdin=page["body"])
    else:
        folder, _, stem = f"{dest.rstrip('/')}/{place or page['title']}".rpartition("/")
        rc, answer = ops_json("page", "create", f"title={stem}", f"dest={folder}", *pairs, "--stdin", stdin=page["body"])
        if rc == 0 and stem != page["title"]:
            # The filename is the title at create; the page's own title is the course's whole name for it.
            rc, answer = ops_json("page", "edit", answer.get("path") or path, f"title={page['title']}")
    if rc != 0:
        return None, f"{page['title']}: {answer.get('error') or answer}", False
    return answer.get("path") or path, None, False


def has_root(dest: str) -> bool | None:
    """Whether `dest` holds its bundle root, by the plugin's own root rule (`page ls filter=prop:root`); None where it cannot say."""
    rc, answer = ops_json("page", "ls", "filter=prop:root", f"filter=under:{dest}")
    if rc != 0 or not isinstance(answer.get("pages"), list):
        return None
    folder = dest.strip("/")
    return any(str(Path(row.get("path") or "").parent) == folder for row in answer["pages"] if isinstance(row, dict))


CURRENT = {"true": "true", "yes": "true", "false": "false", "no": "false"}


def write_root(capture: Path, cap: dict, dest: str, options: dict, root: dict | None = None, overview: str | None = None) -> str | None:
    """Make the course's bundle root once, ever: a root that exists is a person's, and one a person deleted stays deleted.
    The marker in the course's own capture says it was made. The job's `root` keys go on it over the unit's. The refusal, or None."""
    marker = capture / ROOT_MADE
    if marker.exists():
        return None
    word = options.get("current", True)
    current = CURRENT.get(str(word).strip().lower())
    if current is None:
        return f"{ROOT}: options.current={word!r} is not one of true, false, yes, no: no root made"
    found = has_root(dest)
    if found is None:
        return f"{ROOT}: `page ls filter=prop:root` did not answer, so no root was made"
    if not found:
        made = bbnotes.root_page(cap, json.loads((capture / cap["body"]).read_text(encoding="utf-8")), current == "true", overview)
        keys = {**made["fields"], **{k: ("true" if v is True else "false" if v is False else str(v)) for k, v in (root or {}).items()}}
        why = create_root(dest, made, keys)
        if why:
            return why
    marker.write_text(json.dumps({"dest": dest, "made": not found}) + "\n", encoding="utf-8")
    return None


def create_root(folder: str, made: dict, keys: dict) -> str | None:
    """`README.md` in `folder` with `keys`, then its title: the filename is the title at create."""
    pairs = [f"{k}={v}" for k, v in keys.items()] + [f"abstract={made['abstract']}"]
    rc, answer = ops_json("page", "create", f"title={ROOT.removesuffix('.md')}", f"dest={folder}", "type=document", *pairs,
                          "--stdin", stdin=made["body"])
    if rc == 0:
        rc, answer = ops_json("page", "edit", answer.get("path") or f"{folder.rstrip('/')}/{ROOT}", f"title={made['title']}")
    return f"{folder.rstrip('/')}/{ROOT}: {answer.get('error') or answer}" if rc != 0 else None


def write_module_roots(capture: Path, cap: dict, dest: str, record: dict, folders: dict[str, str], overview: str | None) -> list[str]:
    """Each released module's folder root, once, as the course root is: `modules-made.json` in the course capture names the
    modules settled, so a module root a person deleted stays deleted. The refusals."""
    marker = capture / MODULES_MADE
    try:
        made = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        made = {}
    refused = []
    for module in record.get("modules") or []:
        mid = module.get("id")
        if not mid or mid in made:
            continue
        folder = folders.get(mid) or module["folder"]
        if mid not in folders:
            found = has_root(f"{dest.rstrip('/')}/{folder}")
            if found is None:
                refused.append(f"{folder}/{ROOT}: `page ls filter=prop:root` did not answer, so no module root was made")
                continue
            if not found:
                made_root = bbnotes.module_root(cap, module, overview)
                why = create_root(f"{dest.rstrip('/')}/{folder}", made_root, made_root["fields"])
                if why:
                    refused.append(why)
                    continue
        made[mid] = folder
    marker.write_text(json.dumps(made, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return refused


def case_twins(dest: str) -> list[str]:
    """A folder beside `dest` whose name differs from it only by case: one directory on a case-insensitive disk, two to git."""
    path = Path(dest.rstrip("/"))
    try:
        return [p.as_posix() for p in path.parent.iterdir() if p.is_dir() and p.name != path.name and p.name.casefold() == path.name.casefold()]
    except OSError:
        return []


def removed(ticket_id: str, capture: Path, cap: dict, known: dict[str, dict]) -> int:
    """An item the course no longer lists: its page keeps its text and gains `removed: <day>`, which a later pull that finds the
    item again clears. A page a person moved is theirs."""
    # The item's page and a discussion's later parts (`<item>#part-<n>`), each where `known[]` says it is.
    rows = [r for res, r in sorted(known.items()) if res == cap["item"] or res.startswith(f"{cap['item']}#part-")]
    rows = [r for r in rows if r.get("path") and r.get("reason") != "moved"]
    dated = capture / bbnotes.DATED
    if not rows:
        dated.write_text(json.dumps(cap["removed"]) + "\n", encoding="utf-8")
        post_update(ticket_id, "process", "ok", reason="no longer in the course; no page of this job's to date")
        return 0
    written, refused = [], []
    for row in rows:
        rc, answer = ops_json("page", "edit", row["path"], f"removed={cap['removed']}")
        (written if rc == 0 else refused).append(row["path"] if rc == 0 else f"{row['path']}: {answer.get('error') or answer}")
    (capture / WRITTEN).write_text(json.dumps(written) + "\n", encoding="utf-8")
    if refused:
        # Not dated: the next pull posts the stamp again.
        post_update(ticket_id, "process", "partial" if written else "failed", reason="; ".join(refused)[:400],
                    written_from=(capture / WRITTEN).as_posix())
        return 0
    dated.write_text(json.dumps(cap["removed"]) + "\n", encoding="utf-8")
    post_update(ticket_id, "process", "ok", reason=f"{', '.join(written)}: no longer in the course since {cap['removed']}"[:600],
                written_from=(capture / WRITTEN).as_posix())
    return 0


def main(argv: list[str]) -> int:
    ticket_id = next((a.split("=", 1)[1] for a in argv if a.startswith("ticket=")), None)
    if not ticket_id:
        print("process.py: needs ticket=<id>", file=sys.stderr)
        return 7
    t = open_ticket(ticket_id, stage="process")
    capture, dest = Path(t["capture_dir"]), t.get("dest")
    if not dest or not (capture / bbnotes.CAPTURE).is_file():
        post_update(ticket_id, "process", "failed", reason=f"{capture} holds no {bbnotes.CAPTURE}, or the job names no dest")
        return 0
    cap = json.loads((capture / bbnotes.CAPTURE).read_text(encoding="utf-8"))
    if any(h.get("resource") == cap["item"] for h in t.get("held") or []):
        post_update(ticket_id, "process", "ok", reason="a person holds this page: nothing written")
        return 0
    zone = (t.get("options") or {}).get("timezone") or None
    try:
        bbnotes.set_zone(zone)
    except (ValueError, KeyError):
        post_update(ticket_id, "process", "failed", reason=f"options.timezone={zone!r} is no IANA zone this machine knows")
        return 0
    known = {k["resource"]: k for k in t.get("known") or [] if k.get("resource") and k.get("path")}
    written, refused, thin, left, clashed = [], [], [], [], []
    if cap.get("removed"):
        return removed(ticket_id, capture, cap, known)
    folders = module_folders(dest)
    # Where a module's pages go: its root's folder, else where most of its pages now sit, else the ledger's plan.
    try:
        ledger = json.loads((capture.parent / bbnotes.LEDGER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = {}
    homes = {**module_homes(cap, dest, known, ledger if isinstance(ledger, dict) else {}), **folders}
    links = link_paths(cap, dest, known, homes)
    try:
        pages = bbnotes.render(capture, links)
    except (OSError, ValueError, KeyError) as exc:
        post_update(ticket_id, "process", "failed", reason=f"render failed: {type(exc).__name__}: {exc}"[:400])
        return 0
    if cap.get("kind") == "course":
        record = json.loads((capture / cap["body"]).read_text(encoding="utf-8"))
        overview = links.get(bbnotes.cap_key(cap))
        if why := write_root(capture, cap, dest, t.get("options") or {}, t.get("root") or {}, overview):
            refused.append(why)
        refused += write_module_roots(capture, cap, dest, record, folders, overview)
        left += [f"{twin} differs from {dest} only by case: one folder on a case-insensitive disk, two to git" for twin in case_twins(dest)]
    fields = dict(cap.get("fields") or {})
    if cap.get("part_of") and cap["part_of"] in links:
        owner = (cap.get("links") or {}).get(cap["part_of"]) or {}
        fields["part_of"] = f"[[{links[cap['part_of']]}|{owner.get('title') or cap['part_of']}]]"
    place = placed(cap.get("place"), cap.get("module"), homes)
    for n, page in enumerate(pages, 1):
        resource = cap["item"] if n == 1 else f"{cap['item']}#part-{n}"
        row = known.get(resource) or {}
        if row.get("reason") == "moved":
            left.append(f"{row['path']}: moved by a person, left alone")
            continue
        here = place if n == 1 or not place else f"{place} (part {n})"
        path, why, clash = write_page(page, resource, dest, row.get("path"), here, fields)
        if path:
            written.append(path)
        else:
            (clashed if clash else refused).append(why)
        if page.get("problem"):
            thin.append(f"{page['title']}: {page['problem']}")
    (capture / WRITTEN).write_text(json.dumps(written) + "\n", encoding="utf-8")
    status = "failed" if refused and not (written or clashed) else "partial" if refused or thin or clashed else "ok"
    reason = "; ".join(clashed + refused + thin + left)[:600] or None
    post_update(ticket_id, "process", status, reason=reason, written_from=(capture / WRITTEN).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
