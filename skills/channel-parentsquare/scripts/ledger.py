#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""One ParentSquare day's ledger, written from the items the harvest left.

  ledger.py <capture_dir> --ticket <id> [--from lines.json] [--partial <reason>]

`<capture_dir>` is the ticket's own `capture_dir`, VERBATIM — the job's day
directory, `_raw/<slug>/<YYYY-MM-DD>`, wiki-relative: `llm-wiki-ops run`
starts a script at the wiki root. `--ticket` is read through `tickets open`
for the `capture_dir`, `slug` and `dest`; a run with no ticket is refused.

It reads `<capture_dir>/items/*.json`, oldest first by file name, and takes
the process step's judgment from `--from` (a bare name is looked for in the
capture directory; absent, `lines.json` there when it is there, else none):

    [{"id": "parentsquare:<id>", "line": "<one line, in the WIKI's words>" | null,
      "junk": null | "<the rule that discards it>"}]

A row is needed only for an item the step judged: a discard, or a line in
the wiki's words. An item no row names keeps its bullet, `<school>: <subject>`
with what a bullet's folding would leave live swapped for look-alikes. The
page is regenerated WHOLE through `page create`, or `page edit` over the day's
page a pull of the same day left: one bullet per kept item, `- <line> — <id>`,
then `discarded: N (junk rules)`. Then `written.json` and `tickets update`.

Wiki-owned, stdlib only, imports nothing from the plugin.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

OPS = "llm-wiki-ops"
ITEMS_DIRNAME = "items"
LINES_NAME = "lines.json"
LEDGER_TYPE = "ledger"
BULLET_MAX = 200  # the plugin extractor's cap, so a ledger reads the same from either writer
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Look-alikes for the characters a bullet's folding leaves live, the same table channel-gmail's ledger uses.
_SWAPS = str.maketrans({"<": "‹", ">": "›", "—": "-", "―": "-", "*": "∗", "|": "¦"})
_WWW = re.compile(r"(?i)\bwww\.")
_PLAIN = str.maketrans({"`": "'", "[": "(", "]": ")"})
# What a nested front-door call must NOT inherit: the `cwd=` this script was handed binds it to THIS wiki.
NOT_INHERITED = ("CLAUDE_PROJECT_DIR",)


def front_door() -> list:
    """The front door, as an argv prefix.

    A hosted run exports `LLM_WIKI_OPS`, naming the CLI it was itself reached
    by — a command LINE, not a path — and that is the one spelling a jail is
    sure to carry. Otherwise the bare name on PATH. Empty when there is
    neither."""
    named = os.environ.get("LLM_WIKI_OPS")
    if named:
        return shlex.split(named)
    found = shutil.which(OPS)
    return [found] if found else []


def open_ticket(ticket: str, stage: str | None = None) -> dict:
    """This worker's own ticket (A-1), through the front door. Exits naming
    the refusal."""
    me = Path(__file__).stem
    door = front_door()
    if not door:
        sys.exit(f"{me}: `{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing — the front door is how this unit reaches the plugin")
    argv = [*door, "--json", "tickets", "open", ticket]
    if stage:
        argv.append(f"stage={stage}")
    cp = subprocess.run(argv, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit(f"{me}: `tickets open {ticket}` refused — {(cp.stdout + cp.stderr).strip()}")
    try:
        return json.loads(cp.stdout)["ticket"]
    except (ValueError, KeyError) as exc:
        sys.exit(f"{me}: `tickets open {ticket}` did not answer a ticket ({exc}) — {cp.stdout}")


def post_update(
    ticket: str,
    stage: str,
    status: str,
    *,
    reason: str | None = None,
    captured=(),
    missing=(),
    written_from: str | None = None,
    produced: int | None = None,
    note: str | None = None,
) -> int:
    """This worker's progress (A-2), through the front door. `missing` is an
    iterable of `(host, url, why)`; a `,` inside `url` is typed as `%2C`,
    the side note every unit's `missing=` build follows the same way."""
    me = Path(__file__).stem
    door = front_door()
    if not door:
        sys.exit(f"{me}: `{OPS}` is not on PATH and `LLM_WIKI_OPS` names nothing — the front door is how this unit posts progress")
    argv = [*door, "--json", "tickets", "update", ticket, f"stage={stage}", f"status={status}"]
    if reason:
        argv.append(f"reason={reason}")
    for directory in captured:
        argv.append(f"captured={directory}")
    for host, url, why in missing:
        argv.append(f"missing={host},{url.replace(',', '%2C')},{why}")
    if written_from:
        argv.append(f"written_from={written_from}")
    if produced is not None:
        argv.append(f"produced={produced}")
    if note:
        argv.append(f"note={note}")
    cp = subprocess.run(argv, capture_output=True, text=True)
    if cp.returncode != 0:
        print(f"{me}: `tickets update` refused — {(cp.stdout + cp.stderr).strip()}", file=sys.stderr)
    return cp.returncode


# ----------------------------------------------------------------- shared helpers


def _text(value):
    return value if isinstance(value, str) else None


def _read_json(path):
    try:
        found = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _write_json(path, doc):
    """Whole or not at all: a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name.lstrip('.')}.tmp")  # dot-first: never a bullet if a crash leaves it
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def id_in(name):
    """The id an item file is named for — EXACTLY: `<stamp>--<id>.json`, dot or
    no dot. A stamp never carries `--`; an id may, so the split is the first."""
    stem = name[1:] if name.startswith(".") else name
    _stamp, sep, rest = stem.partition("--")
    return rest[: -len(".json")] if sep and rest.endswith(".json") else None


def host_line(value):
    """A venue's own line with what a bullet's folding leaves open swapped
    out. A folding pass turns a backtick and the two square brackets and caps
    the line; it leaves raw HTML, the ` — ` a bullet puts before its pointer,
    a bare url a renderer autolinks, `*` emphasis and a table's `|`.
    Look-alikes, not deletions: the line still reads as what was written."""
    return _WWW.sub("www․", value.translate(_SWAPS).replace("://", ":∕∕"))


def bullet_line(value):
    """One item's text as one bullet's worth: folded to a single line, the
    look-alikes `host_line` swaps, the three characters `extract.py::_plain`
    turns, and capped. Whoever writes the day's page — this step, or the
    plugin's extractor over the same items — a bullet reads the same and
    forges nothing."""
    folded = host_line(" ".join(str(value).split()).translate(_PLAIN))
    return folded[: BULLET_MAX - 1] + "…" if len(folded) > BULLET_MAX else folded


def _said(done):
    return " ".join((done.stderr or done.stdout or "").split())[:300]


# ----------------------------------------------------------------- the ledger


def read_items(day_dir):
    """The day's item files, oldest first — the filename is the time."""
    items_dir = day_dir / ITEMS_DIRNAME
    paths = sorted(p for p in items_dir.iterdir() if p.is_file() and not p.name.startswith(".") and id_in(p.name)) if items_dir.is_dir() else []
    return [(p.name, _read_json(p)) for p in paths]


def verdicts_in(rows):
    """`{"<pointer>": {"line": …, "junk": …}}`; a row with no id names no item and is dropped."""
    found = {}
    for row in rows if isinstance(rows, list) else []:
        pointer = _text(row.get("id")) if isinstance(row, dict) else None
        if pointer:
            found[pointer] = row
    return found


def ledger_body(items, verdicts):
    """`(body, kept, discarded, from_subject)`: one bullet per kept item in file order, then the junk tally."""
    bullets, discarded, from_subject = [], 0, 0
    for name, doc in items:
        pointer = _text(doc.get("id")) or f"parentsquare:{id_in(name)}"
        verdict = verdicts.get(pointer) or {}
        if (_text(verdict.get("junk")) or "").strip():
            discarded += 1
            continue
        line = (_text(verdict.get("line")) or "").strip()
        if not line:
            from_subject += 1
            school, subject = (_text(doc.get("school")) or "").strip(), (_text(doc.get("subject")) or "").strip()
            line = f"{school}: {subject}" if school and subject else subject or school
        head = f"{bullet_line(line)} — " if line else ""
        bullets.append(f"- {head}{bullet_line(pointer)}")
    return "\n".join(bullets) + f"\n\ndiscarded: {discarded} (junk rules)\n", len(bullets), discarded, from_subject


def _ops(argv, body):
    """The front door as an argument list, never a shell line: every value here is venue text one step removed."""
    env = {key: value for key, value in os.environ.items() if key not in NOT_INHERITED}
    try:
        return subprocess.run([*(front_door() or [OPS]), *argv], input=body, capture_output=True, text=True, env=env, check=False)
    except OSError as exc:
        return subprocess.CompletedProcess(argv, 127, "", f"could not start {OPS}: {type(exc).__name__}: {exc}")


def write_page(dest, day, keys, body):
    """`(<wiki-relative path>, None)`, or `(None, <why>)`. A second pull of the day finds the page made: edit it whole.
    `status=` clears the draft box create would set; an edit may not carry it, and the page it edits has none."""
    rel = f"{dest.rstrip('/')}/{day}.md"
    made = _ops(["page", "create", f"title={day}", f"dest={dest}", *keys, "status=", "--stdin"], body)
    if made.returncode == 0:
        return rel, None
    edited = _ops(["page", "edit", rel, *keys, "--stdin"], body)
    if edited.returncode == 0:
        return rel, None
    return None, f"`page create` said {_said(made)!r}; `page edit` said {_said(edited)!r}"


def lines_from(directory, given):
    """The step's rows, or `[]` where it wrote none; raises on a file that is there and not JSON."""
    if given == "-":
        raw = sys.stdin.read()
    else:
        path = directory / LINES_NAME if given is None else Path(given)
        if given is not None and not path.is_absolute() and len(path.parts) == 1:
            path = directory / path
        if given is None and not path.is_file():
            return []
        raw = path.read_text(encoding="utf-8")
    return json.loads(raw) if raw.strip() else []


def ledger(directory, args):
    ticket = open_ticket(args.ticket, "process")
    named = ticket.get("capture_dir")
    directory = Path(named) if isinstance(named, str) and named else directory
    day = directory.name
    dest = str(ticket.get("dest") or "").strip().rstrip("/")

    def finish(outcome, reason, *, written=(), counts=None):
        written_from = None
        if written:
            written_from = "written.json"
            _write_json(directory / written_from, list(written))
        if post_update(args.ticket, "process", outcome, reason=reason, written_from=written_from):
            print("ledger: `tickets update` refused — the report above did not land", file=sys.stderr)
        print(json.dumps({"outcome": outcome, "reason": reason, "written": list(written), **(counts or {})}, indent=2))
        return 1 if outcome == "failed" else 0

    if not dest:
        print("ledger: the ticket names no `dest` — a process ticket carries the job's ledger route, wiki-relative", file=sys.stderr)
        return 2
    items = read_items(directory)
    if not items:
        return finish("ok", f"{day} holds no {ITEMS_DIRNAME}/ item to write a ledger from")
    try:
        rows = lines_from(directory, args.source)
    except (OSError, ValueError) as exc:
        return finish("failed", f"the lines could not be read: {type(exc).__name__}: {exc}")
    body, kept, discarded, from_subject = ledger_body(items, verdicts_in(rows))
    counts = {"items": len(items), "kept": kept, "discarded": discarded, "from_subject": from_subject}
    keys = [f"type={LEDGER_TYPE}", f"channel={ticket.get('slug') or day}", f"date={day}", f"items={kept}", "extracted=true"]
    rel, why = write_page(dest, day, keys, body)
    if rel is None:
        return finish("failed", f"the ledger was not written: {why}", counts=counts)
    return finish("partial" if args.partial else "ok", args.partial or None, written=[rel], counts=counts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("capture_dir", help="the ticket's own `capture_dir`, wiki-relative: the job's day directory")
    parser.add_argument("--ticket", required=True, help="the ticket id, read through `tickets open` for every other input")
    parser.add_argument("--from", dest="source", help=f"the step's rows as a JSON file: a bare name is looked for IN the capture directory, `-` is stdin; absent, `{LINES_NAME}` there if any")
    parser.add_argument("--partial", metavar="REASON", help="only some of the day was judged, and why")
    args = parser.parse_args(argv)
    directory = Path(args.capture_dir)
    if not DAY_RE.fullmatch(directory.name):
        print(f"ledger: {args.capture_dir!r} is not a day directory — give the ticket's own `capture_dir` (`_raw/<slug>/<YYYY-MM-DD>`)", file=sys.stderr)
        return 2
    return ledger(directory, args)


if __name__ == "__main__":
    sys.exit(main())
