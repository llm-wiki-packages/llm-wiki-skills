#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The two names a ParentSquare item file needs, computed from text that never touches a shell.

  keys.py notice <draft.json>          prints ps-notice-<school_id>-<12 hex of sha1(title|date)>
  keys.py stamp <draft.json> [--now MS]  prints the 13-digit epoch milliseconds of the post's date

`<draft.json>` is a file the session wrote with its file-writing tool: the
served title and date are venue text, so they ride a JSON file and never a
command line. A notice has no id of its own in the server (0.4.0), and its
place in the list shifts, so its key is its content. A date that does not
parse stamps the pull's own clock.

Wiki-owned, stdlib only.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone

DATE_FORMATS = ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y", "%m/%d/%Y", "%m/%d/%y")


def refuse(why):
    print(f"keys: {why}", file=sys.stderr)
    sys.exit(2)


def read_draft(path):
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (OSError, ValueError) as exc:
        refuse(f"{path} is not a readable JSON file: {exc}")
    if not isinstance(doc, dict):
        refuse(f"{path} is not a JSON object")
    return doc


def text_of(doc, field):
    value = doc.get(field)
    if not isinstance(value, str):
        refuse(f"draft field {field} is not a string")
    return value.strip()


def notice_key(doc):
    school = doc.get("school_id")
    if isinstance(school, bool) or not isinstance(school, int) or school < 0:
        refuse(f"draft field school_id must be a whole number, got {school!r}")
    digest = hashlib.sha1(f"{text_of(doc, 'title')}|{text_of(doc, 'date')}".encode("utf-8")).hexdigest()
    return f"ps-notice-{school}-{digest[:12]}"


def stamp(doc, now):
    served = text_of(doc, "date")
    for form in DATE_FORMATS:
        try:
            day = datetime.strptime(served, form)
        except ValueError:
            continue
        return int(day.replace(hour=12, tzinfo=timezone.utc).timestamp() * 1000)
    return now


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    arms = parser.add_subparsers(dest="arm", required=True)
    arms.add_parser("notice").add_argument("draft")
    one = arms.add_parser("stamp")
    one.add_argument("draft")
    one.add_argument("--now", type=int, default=None, help="the pull's clock in epoch milliseconds (default: now)")
    args = parser.parse_args(argv)
    doc = read_draft(args.draft)
    if args.arm == "notice":
        print(notice_key(doc))
    else:
        print(f"{stamp(doc, args.now if args.now is not None else int(time.time() * 1000)):013d}")


if __name__ == "__main__":
    main()
