#!/usr/bin/env python3
"""The attended modes' pull: messages off ONE mailbox through gws, as JSON.

  gmail_pull.py --out FILE [--query 'is:unread in:inbox'] [--max 50]
                [--bodies] [--mailbox ADDR] [--config-dir DIR]

Read-only: `getProfile`, `messages list`, `messages get`. Writes one JSON
list, newest first (Gmail's order), to `--out`, and prints a one-line
summary. Each record:

  {id, thread, internal_date, date, from, to, cc, subject, labels, snippet,
   list_unsubscribe, attachments: [{name, mime}], body}

`body` is the plain-text part, present only with `--bodies` — triage
classifies on headers and the snippet. `--mailbox` asserts the login is
signed into that address and refuses otherwise; `--config-dir` picks the
gws login directory (default: gws's own, `~/.config/gws`).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gwscli


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--query", default="is:unread in:inbox", help="Gmail search (default: is:unread in:inbox)")
    ap.add_argument("--max", type=int, default=50, help="cap on messages, newest first (default 50)")
    ap.add_argument("--bodies", action="store_true", help="keep the plain-text bodies")
    ap.add_argument("--mailbox", help="refuse unless the login is signed into this address")
    ap.add_argument("--config-dir", help="the gws login directory for this mailbox")
    ap.add_argument("--out", required=True, help="where the JSON list is written")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    try:
        if a.mailbox:
            me = gwscli.profile(a.config_dir)
            if me.casefold() != a.mailbox.casefold():
                print(f"gmail_pull: the login is {me!r}, not {a.mailbox!r} — refusing to pull", file=sys.stderr)
                return 2
        ids, _ = gwscli.list_ids(a.query, a.config_dir, limit=max(1, a.max))
        with ThreadPoolExecutor(max_workers=max(1, a.workers)) as pool:
            records = list(pool.map(lambda mid: gwscli.fetch(mid, a.config_dir), ids))
    except gwscli.GwsError as exc:
        print(f"gmail_pull: {exc.said}", file=sys.stderr)
        return 2 if exc.why == "auth" else 1
    if not a.bodies:
        for one in records:
            one.pop("body", None)
    Path(a.out).write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"written": a.out, "count": len(records), "query": a.query}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
