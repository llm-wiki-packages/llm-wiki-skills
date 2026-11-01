#!/usr/bin/env python3
"""The Blackboard process stage: one capture into its page(s) under the job's dest. No model session, no network.

  llm-wiki-ops run ops/skills/channel-blackboard/scripts/process.py ticket=<id>

Reads the ticket through `tickets open`; its `capture_dir` is one item
directory `harvest.py` posted. `bbnotes.render` makes the page: a content
item's text and due date, a pdf, slide deck or Word file's text, a video's
transcript, an announcement, a discussion board's posts (in parts past
60 KB), or the course overview. Each page is written through `page create`,
or `page edit` where it exists already — at `dest`, or where a person moved it
(`known[]`'s `path`). A capture a person holds (`held[]`) writes nothing.

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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bbnotes  # noqa: E402
from door import open_ticket, ops_json, post_update  # noqa: E402

WRITTEN = "written.json"


def write_page(page: dict, cap: dict, dest: str, moved_to: str | None) -> tuple[str | None, str | None]:
    pairs = [f"type={page['type']}", f"resource={cap['item']}", "extracted=true"]
    if page.get("published"):
        pairs.append(f"published={page['published']}")
    path = moved_to or f"{dest.rstrip('/')}/{page['title']}.md"
    if Path(path).is_file():
        rc, answer = ops_json("page", "edit", path, *pairs, "--stdin", stdin=page["body"])
    else:
        rc, answer = ops_json("page", "create", f"title={page['title']}", f"dest={dest}", *pairs, "--stdin", stdin=page["body"])
    if rc != 0:
        return None, f"{page['title']}: {answer.get('error') or answer}"
    return answer.get("path") or path, None


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
    bbnotes.set_zone((t.get("options") or {}).get("timezone") or None)
    try:
        pages = bbnotes.render(capture)
    except (OSError, ValueError, KeyError) as exc:
        post_update(ticket_id, "process", "failed", reason=f"render failed: {type(exc).__name__}: {exc}"[:400])
        return 0
    known = {k.get("path"): k for k in t.get("known") or [] if k.get("resource") == cap["item"] and k.get("path")}
    moved = next((p for p, k in known.items() if k.get("reason") == "moved"), None)
    written, refused, thin = [], [], []
    for n, page in enumerate(pages):
        path, why = write_page(page, cap, dest, moved if n == 0 else None)
        if path:
            written.append(path)
        else:
            refused.append(why)
        if page.get("problem"):
            thin.append(f"{page['title']}: {page['problem']}")
    (capture / WRITTEN).write_text(json.dumps(written) + "\n", encoding="utf-8")
    status = "failed" if refused and not written else "partial" if refused or thin else "ok"
    reason = "; ".join(refused + thin)[:600] or None
    post_update(ticket_id, "process", status, reason=reason, written_from=(capture / WRITTEN).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
