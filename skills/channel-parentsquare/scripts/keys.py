#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The two names a ParentSquare item file needs, computed from text that never touches a shell.

  keys.py notice <draft.json>          prints ps-notice-<school_id>-<12 hex of sha1(title|date)>
  keys.py stamp <draft.json> [--now MS] [--day-dir DIR]
                                       prints the 13-digit epoch milliseconds of the post's date

`<draft.json>` is a file the session wrote with its file-writing tool: the
served title and date are venue text, so they ride a JSON file and never a
command line. A notice has no id of its own in the server (0.4.0), and its
place in the list shifts, so its key is its content.

A served date is the `data-timestamp` attribute verbatim or, without one, the
element's text, and the server's source pins neither shape. `stamp` reads
ISO-8601 (offset, `Z`, fractional seconds, no zone read as UTC, or a date
alone at noon UTC), epoch seconds, epoch milliseconds, and a month name with
or without a year. A date none of those match stamps the pull's clock, unless
`--day-dir` holds an `items/<stamp>--<id>.json` for the draft's `id`: its
stamp is reused, so a re-pull rewrites that file instead of adding a second.

Wiki-owned, stdlib only.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
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


def parsed(served, now):
    """Epoch milliseconds of a served date, or None where no shape matches."""
    if re.fullmatch(r"\d{13}", served):
        return int(served)
    if re.fullmatch(r"\d{9,10}(\.\d+)?", served):
        return int(float(served) * 1000)
    try:
        moment = datetime.fromisoformat(served)
    except ValueError:
        moment = None
    if moment is not None:
        if moment.tzinfo is None:
            moment = moment.replace(hour=12) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", served) else moment
            moment = moment.replace(tzinfo=timezone.utc)
        return round(moment.timestamp() * 1000)
    for form in DATE_FORMATS:
        try:
            day = datetime.strptime(served, form)
        except ValueError:
            continue
        return int(day.replace(hour=12, tzinfo=timezone.utc).timestamp() * 1000)
    year = datetime.fromtimestamp(now / 1000, timezone.utc).year
    for form in ("%b %d %Y", "%B %d %Y"):
        try:
            day = datetime.strptime(f"{served} {year}", form).replace(hour=12, tzinfo=timezone.utc)
        except ValueError:
            continue
        if day.timestamp() * 1000 > now:
            day = day.replace(year=year - 1) if not (day.month == 2 and day.day == 29) else day.replace(year=year - 4)
        return int(day.timestamp() * 1000)
    return None


ID_RE = re.compile(r"^ps-(post|notice)-[A-Za-z0-9-]+$")


def held_stamp(doc, day_dir):
    """The stamp of this item's own file already in the day, or None."""
    item = doc.get("id")
    if day_dir is None or not isinstance(item, str):
        return None
    if not ID_RE.fullmatch(item):
        refuse(f"draft field id {item!r} is not a ps-post-/ps-notice- id")
    for path in sorted((Path(day_dir) / "items").glob(f"*--{item}.json")):
        head = path.name.split("--", 1)[0].lstrip(".")
        if re.fullmatch(r"\d{13}", head):
            return int(head)
    return None


def stamp(doc, now, day_dir=None):
    found = parsed(text_of(doc, "date"), now)
    if found is None:
        found = held_stamp(doc, day_dir)
    return now if found is None else found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    arms = parser.add_subparsers(dest="arm", required=True)
    arms.add_parser("notice").add_argument("draft")
    one = arms.add_parser("stamp")
    one.add_argument("draft")
    one.add_argument("--now", type=int, default=None, help="the pull's clock in epoch milliseconds (default: now)")
    one.add_argument("--day-dir", default=None, help="the capture directory: an unparseable date reuses the stamp of the draft id's file in its items/")
    args = parser.parse_args(argv)
    doc = read_draft(args.draft)
    if args.arm == "notice":
        print(notice_key(doc))
    else:
        now = args.now if args.now is not None else int(time.time() * 1000)
        print(f"{stamp(doc, now, args.day_dir):013d}")


if __name__ == "__main__":
    main()
