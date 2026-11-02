#!/usr/bin/env python3
"""channel-github's routine — regenerate the list pages from the repo pages.

A script stage, with no model session: a routines job naming this unit runs
it in the routine stage's jail as

    llm-wiki-ops run ops/skills/channel-github/scripts/lists.py [--only <words>] ticket=<id>

It reads its ticket for `dest` (the routines job's, `research/github/<slug>`),
opens the unit's op, writes one `type: list` page per list
`references/lists.json` declares — each regenerated whole through `page
create`, or `page edit` of the list page `page ls` finds by its identity
— and closes the op, which under the ticket is the
report. It never commits: the host commits the pages at the landing.

stdlib only: a script stage refuses a PEP 723 block.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from catalog import build_lists, load_catalog, load_config, today_utc, wiki_root
from door import open_ticket, ops_json

UNIT = "channel-github"
LIST_TAGS = "github,github-list"
DESCRIPTION_MAX = 200
# A list page's identity: one resource for the routine's lists, a list of it per page (`write_list_page`).
LISTS = "github:lists"
LIST = "github:list:"


def identity_match(rows, slug, dest):
    """The one page of job `slug` a `page ls resource=` answer names: `(row, None)`, `(None, None)` where there is none,
    `(None, <why>)` where there are several — never one picked.

    A page is the job's when it is stamped with the job, or unstamped under `dest`: the landing stamps `job`, so a
    page written before it carries none. A row from another job is that job's page, not this one's."""
    folder = str(dest or "").strip("/")
    mine = [
        row
        for row in rows
        if isinstance(row, dict)
        and (row.get("job") == slug or (row.get("job") is None and folder and str(row.get("path") or "").startswith(folder + "/")))
    ]
    if len(mine) > 1:
        return None, "pages " + ", ".join(sorted(str(row.get("path")) for row in mine)) + " all hold this item: none was written"
    return (mine[0] if mine else None), None


def left_alone(row):
    """Why the page `row` names is not this run's to write, or None: a person moved it out of `dest`, or ticked its
    Draft or Archive box."""
    if row.get("moved"):
        return f"{row.get('path')}: moved out of dest by a person, left alone"
    if row.get("draft") or row.get("archive"):
        return f"{row.get('path')}: held (Draft or Archive), left alone"
    return None


def write_list_page(dest: str, title: str, description: str, body: str, slug: str | None = None) -> tuple[str | None, str | None]:
    """`(path, None)` once the page is written, `(None, why)` when the verb refused or the page is left alone.

    A list is found by its identity — `resource=LISTS`, `resource_id=<LIST><title>` — so a list page a person
    renamed is regenerated at the path that lookup found, never made twice. A list page from before lists carried one sits
    at `<dest>/<title>.md` with no `resource`: stamped with it, the one time. A page there naming another resource
    is never written over."""
    pairs = ["type=list", f"tags={LIST_TAGS}", f"description={description[:DESCRIPTION_MAX]}"]
    ident = [f"resource={LISTS}", f"resource_id={LIST}{title}"]
    # Scoped to dest (2026-11-02): in a stage's jail, `page ls` walked from the wiki root lists nothing the jail does not grant.
    rc, answer = ops_json("page", "ls", f"filter=under:{dest}", *ident)
    if rc != 0 or not isinstance(answer.get("pages"), list):
        return None, f"{title}: `page ls` did not answer: {answer.get('error') or answer}"
    row, why = identity_match(answer["pages"], slug, dest)
    if why:
        return None, f"{title}: {why}"
    path = f"{dest.rstrip('/')}/{title}.md"
    if row is not None:
        why = left_alone(row)
        if why:
            return None, f"{title}: {why}"
        path = row["path"]
        # By the path the lookup found (2026-11-02): in a stage's jail, `page edit id=` resolves the id by a walk from the wiki root, which sees nothing.
        rc, answer = ops_json("page", "edit", path, *pairs, "--stdin", stdin=body)
    elif Path(path).is_file():
        rc, held = ops_json("page", "read", path, "--frontmatter")
        front = held.get("frontmatter") if rc == 0 else None
        if not isinstance(front, dict) or front.get("resource"):
            return None, f"{title}: {path} is not this list's, and is not written over"
        rc, answer = ops_json("page", "edit", path, *pairs, *ident, "--stdin", stdin=body)
    else:
        rc, answer = ops_json("page", "create", f"title={title}", f"dest={dest}", *pairs, *ident, "--stdin", stdin=body)
    if rc != 0:
        return None, f"{title}: {answer.get('error') or answer}"
    return answer.get("path") or path, None


def close(outcome: str, summary: str) -> int:
    rc, answer = ops_json("op", "close", UNIT, f"outcome={outcome}", f"summary={summary}")
    if rc != 0:
        print(f"lists: `op close` refused — {answer.get('error') or answer}", file=sys.stderr)
    return rc


def run(ticket_id: str, only: str | None) -> int:
    ticket = open_ticket(ticket_id, "routine")
    cfg = load_config()
    rc, answer = ops_json("op", "open", UNIT)
    if rc != 0:
        print(f"lists: `op open` refused — {answer.get('error') or answer}", file=sys.stderr)
        return 2
    dest = ticket.get("dest")
    if not dest:
        close("failed", "channel-github lists: the routines job names no dest — re-add it with dest=research/github/<slug>")
        return 1
    records = load_catalog(wiki_root(), cfg["repos"], cfg["also"])
    built = build_lists(cfg, records, today_utc())
    if only:
        built = [b for b in built if only.lower() in b[0].lower()]
    written, refused = [], []
    for title, description, body in built:
        path, why = write_list_page(dest, title, description, body, ticket.get("slug"))
        if path:
            written.append(path)
        else:
            refused.append(why)
    outcome = "failed" if refused and not written else "partial" if refused else "ok"
    summary = f"channel-github lists: {len(written)} list pages from {len(records)} repo pages"
    if refused:
        summary += f"; {len(refused)} refused, first: {refused[0][:200]}"
    print(json.dumps({"outcome": outcome, "written": written, "refused": refused, "repo_pages": len(records)}, indent=1))
    return 0 if close(outcome, summary) == 0 and outcome != "failed" else 1


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # The runner appends `ticket=<id>` after the routine entry's `args`.
    ticket = next((a.split("=", 1)[1] for a in args if a.startswith("ticket=")), None)
    parser = argparse.ArgumentParser(prog="lists.py", usage="lists.py [--only <words>] ticket=<id>")
    parser.add_argument("--only", help="only the list pages whose title contains this")
    known, _rest = parser.parse_known_args([a for a in args if not a.startswith("ticket=")])
    if not ticket:
        parser.error("ticket=<id> is required: a routines job runs this script; preview a list with `catalog.py preview`")
    return run(ticket, known.only)


if __name__ == "__main__":
    sys.exit(main())
