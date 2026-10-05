#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""The pull `channel-notion-tasks`' harvest stage makes: the tasks edited since a
moment, read through `ntn`, written to `<capture_dir>/pull.json` for
`write_items.py write --from pull.json`.

  pull.py <capture_dir> --workspace <name> --since <ISO-8601> \\
          --database <id>... [--deadline-seconds N]

Every `ntn` call lives here, so the session that runs this script holds no
Notion command of its own. Reading only: `whoami`, `datasources resolve`,
`api .../query` and `pages get`, each with stdin given (`ntn` waits on it
until the slice dies otherwise). The login is never read here: the stage's
sandbox names a `notion` route, `NOTION_API_TOKEN` holds a phantom in this
jail, and the proxy puts the wiki's own token on the request.

Answers one JSON object on stdout and exits 0 when it wrote `pull.json`
(`ok`, or `partial` with the reason to pass on as `write --partial`), 3 when
nothing was pulled (`failed`, naming `why`: `denied`, `timeout`, `auth` or
`error`), 2 on a bad argument. A workspace that is not `--workspace` is `auth`.

Tasks are written oldest first. `--deadline-seconds` bounds the whole pull so a
slice's own kill never lands mid-write: past it the run stops, keeps what it
has, and says `partial`.

Wiki-owned, stdlib only, imports nothing from the plugin.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

NTN = "ntn"
PAGE_SIZE = 100
CALL_TIMEOUT = 120
DEADLINE_SECONDS = 1500  # a slice dies at 30 minutes; leave room to write
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n?", re.S)
AUTH_WORDS = ("401", "unauthorized", "unauthenticated", "invalid token", "api token is invalid", "restricted")
DENIED_WORDS = ("403", "forbidden", "denied", "proxy")
TIMEOUT_WORDS = ("timed out", "timeout")


class Failed(Exception):
    def __init__(self, why, reason):
        super().__init__(reason)
        self.why = why
        self.reason = reason


def why_of(text):
    low = text.lower()
    for why, words in (("auth", AUTH_WORDS), ("denied", DENIED_WORDS), ("timeout", TIMEOUT_WORDS)):
        if any(word in low for word in words):
            return why
    return "error"


def ntn(*args, stdin=None):
    """One `ntn` call, its stdout; stdin is always given."""
    exe = shutil.which(NTN)
    if not exe:
        raise Failed("error", "`ntn` is not on PATH")
    try:
        cp = subprocess.run(
            [exe, *args], input=stdin if stdin is not None else "", capture_output=True, text=True,
            timeout=CALL_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        raise Failed("timeout", f"`ntn {args[0]}` timed out after {CALL_TIMEOUT}s")
    if cp.returncode != 0:
        detail = (cp.stderr or cp.stdout).strip().splitlines()
        raise Failed(why_of(cp.stderr + cp.stdout), f"`ntn {' '.join(args[:2])}` exited {cp.returncode}: {detail[-1][:200] if detail else ''}")
    return cp.stdout


def ntn_json(*args, stdin=None):
    out = ntn(*args, stdin=stdin)
    try:
        return json.loads(out)
    except ValueError:
        raise Failed("error", f"`ntn {args[0]}` did not answer JSON")


def data_source_ids(answer):
    """The data source ids a `datasources resolve` answer names, in order."""
    if isinstance(answer, dict):
        for key in ("data_sources", "results"):
            if isinstance(answer.get(key), list):
                answer = answer[key]
                break
        else:
            answer = [answer]
    ids = []
    for entry in answer if isinstance(answer, list) else []:
        sid = entry.get("id") if isinstance(entry, dict) else entry if isinstance(entry, str) else None
        if sid:
            ids.append(sid)
    return ids


def text_of(rich):
    return "".join(part.get("plain_text", "") for part in rich or [] if isinstance(part, dict))


def fields_of(properties):
    """title, status, due and assignee, off a page's `properties` — a field the page does not carry is None."""
    out = {"title": None, "status": None, "due": None, "assignee": None}
    for prop in (properties or {}).values():
        if not isinstance(prop, dict):
            continue
        kind = prop.get("type")
        value = prop.get(kind) if kind else None
        if kind == "title" and out["title"] is None:
            out["title"] = text_of(value)
        elif kind in ("status", "select") and out["status"] is None and isinstance(value, dict):
            out["status"] = value.get("name")
        elif kind == "date" and out["due"] is None and isinstance(value, dict):
            out["due"] = value.get("start")
        elif kind == "people" and out["assignee"] is None and isinstance(value, list):
            names = [p.get("name") for p in value if isinstance(p, dict) and p.get("name")]
            out["assignee"] = ", ".join(names) or None
    return out


def body_of(page_markdown):
    """The notes `pages get` prints after its frontmatter."""
    return FRONTMATTER.sub("", page_markdown, count=1).strip()


def query(source_id, since, deadline):
    """Every page of one data source edited on or after `since`, oldest first, and whether the deadline cut it short."""
    start = None
    while True:
        if time.monotonic() > deadline:
            yield None
            return
        body = {
            "filter": {"timestamp": "last_edited_time", "last_edited_time": {"on_or_after": since}},
            "sorts": [{"timestamp": "last_edited_time", "direction": "ascending"}],
            "page_size": PAGE_SIZE,
        }
        if start:
            body["start_cursor"] = start
        answer = ntn_json("api", f"v1/data_sources/{source_id}/query", stdin=json.dumps(body))
        yield from answer.get("results") or []
        if not answer.get("has_more"):
            return
        start = answer.get("next_cursor")
        if not start:
            return


def pull(args, deadline):
    who = ntn_json("whoami", "--json")
    workspace = ((who.get("bot") or {}).get("workspace_name")) if isinstance(who, dict) else None
    if workspace != args.workspace:
        raise Failed("auth", f"the token reaches workspace {workspace!r}, not {args.workspace!r}")
    tasks, partial = [], None
    for database in args.database:
        for source in data_source_ids(ntn_json("datasources", "resolve", database, "--json")):
            for page in query(source, args.since, deadline):
                if page is None:
                    partial = f"the {args.deadline_seconds}s deadline came before every data source was read"
                    break
                if time.monotonic() > deadline:
                    partial = f"the {args.deadline_seconds}s deadline came before every page was read"
                    break
                fields = fields_of(page.get("properties"))
                notes = body_of(ntn("pages", "get", page["id"]))
                tasks.append({
                    "id": page["id"], "last_edited": page.get("last_edited_time"), "database": database,
                    "title": fields["title"], "status": fields["status"], "due": fields["due"],
                    "assignee": fields["assignee"], "url": page.get("url"), "body": notes,
                })
            if partial:
                break
        if partial:
            break
    tasks.sort(key=lambda t: t["last_edited"] or "")
    return tasks, partial


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture_dir", help="the ticket's own `capture_dir`, wiki-relative, verbatim")
    ap.add_argument("--workspace", required=True, help="the job's `options.workspace`")
    ap.add_argument("--since", required=True, help="ISO-8601 UTC, `write_items.py since`'s answer")
    ap.add_argument("--database", action="append", required=True, help="a Notion database id; repeat per database")
    ap.add_argument("--deadline-seconds", type=float, default=DEADLINE_SECONDS)
    args = ap.parse_args(argv)
    directory = Path(args.capture_dir)
    deadline = time.monotonic() + args.deadline_seconds
    try:
        tasks, partial = pull(args, deadline)
    except Failed as exc:
        print(json.dumps({"status": "failed", "why": exc.why, "reason": exc.reason, "url": "https://api.notion.com"}))
        return 3
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pull.json").write_text(json.dumps(tasks, indent=1), encoding="utf-8")
    print(json.dumps({"status": "partial" if partial else "ok", "count": len(tasks), "pull": "pull.json", "partial": partial}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
