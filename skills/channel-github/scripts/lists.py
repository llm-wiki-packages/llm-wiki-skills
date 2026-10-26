#!/usr/bin/env python3
"""channel-github's routine — regenerate the list pages from the repo pages.

A script stage, with no model session: a routines job naming this unit runs
it in the routine stage's jail as

    llm-wiki-ops run ops/skills/channel-github/scripts/lists.py [--only <words>] ticket=<id>

It reads its ticket for `dest` (the routines job's, `research/github/<slug>`),
opens the unit's op, writes one `type: list` page per list
`references/lists.json` declares — each regenerated whole through `page
create` or `page edit` — and closes the op, which under the ticket is the
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


def write_list_page(dest: str, title: str, description: str, body: str) -> tuple[str | None, str | None]:
    """`(path, None)` once the page is written, `(None, why)` when the verb refused."""
    pairs = ["type=list", f"tags={LIST_TAGS}", f"description={description[:DESCRIPTION_MAX]}"]
    path = f"{dest.rstrip('/')}/{title}.md"
    if Path(path).is_file():
        rc, answer = ops_json("page", "edit", path, *pairs, "--stdin", stdin=body)
    else:
        rc, answer = ops_json("page", "create", f"title={title}", f"dest={dest}", *pairs, "--stdin", stdin=body)
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
        path, why = write_list_page(dest, title, description, body)
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
