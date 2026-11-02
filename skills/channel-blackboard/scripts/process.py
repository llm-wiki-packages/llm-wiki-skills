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


def write_page(page: dict, resource: str, dest: str, known_path: str | None) -> tuple[str | None, str | None, bool]:
    """`(path, None, False)` written; `(None, why, True)` a page that is not this item's stood at the path; `(None, why, False)` refused."""
    pairs = [f"type={page['type']}", f"resource={resource}", "extracted=true"]
    if page.get("published"):
        pairs.append(f"published={page['published']}")
    path = known_path or f"{dest.rstrip('/')}/{page['title']}.md"
    if known_path:
        rc, answer = ops_json("page", "edit", path, *pairs, "--stdin", stdin=page["body"])
    elif Path(path).is_file():
        # Not this item's page by `known[]`: edit it only where its own frontmatter says it is.
        other = resource_of(Path(path))
        if other != resource:
            return None, f"{path} holds {'another item, ' + other if other else 'a page no item wrote'}: not written over", True
        rc, answer = ops_json("page", "edit", path, *pairs, "--stdin", stdin=page["body"])
    else:
        rc, answer = ops_json("page", "create", f"title={page['title']}", f"dest={dest}", *pairs, "--stdin", stdin=page["body"])
    if rc != 0:
        return None, f"{page['title']}: {answer.get('error') or answer}", False
    return answer.get("path") or path, None, False


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
    try:
        pages = bbnotes.render(capture)
    except (OSError, ValueError, KeyError) as exc:
        post_update(ticket_id, "process", "failed", reason=f"render failed: {type(exc).__name__}: {exc}"[:400])
        return 0
    known = {k["resource"]: k for k in t.get("known") or [] if k.get("resource") and k.get("path")}
    written, refused, thin, left, clashed = [], [], [], [], []
    for n, page in enumerate(pages, 1):
        resource = cap["item"] if n == 1 else f"{cap['item']}#part-{n}"
        row = known.get(resource) or {}
        if row.get("reason") == "moved":
            left.append(f"{row['path']}: moved by a person, left alone")
            continue
        path, why, clash = write_page(page, resource, dest, row.get("path"))
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
