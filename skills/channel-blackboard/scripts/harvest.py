#!/usr/bin/env python3
"""The Blackboard harvest stage: one course, through the signed-in profile, split into one capture per item. No model session.

  llm-wiki-ops run ops/skills/channel-blackboard/scripts/harvest.py ticket=<id>

The runner starts it that way, in the stage's jail. It reads the ticket
through `tickets open`, runs `bb.py harvest` under the ticket's
`browser_python` on the granted `credential_dir` into
`<capture_dir>/harvest/`, then `bbnotes.split` into `<capture_dir>/items/`,
and posts every item directory that is new or changed since the last pull as
`captured=`. The host turns each into a transcribe ticket (a video whose
words are missing, where the job has a `transcribe` section) and a process
ticket. It never closes the ticket.

The job's target is the course's url (`https://<host>/ultra/courses/_123_1/outline`)
or `<base url>#<course id>`: the host is the site, the `_N_1` id the course.
An item is posted again when its capture's fingerprint moved or no page holds
its resource yet (`known[]`); one a person moved (`reason: moved`) is never
posted. Exit 2 from `bb.py` is an expired session: `failed` with
`missing=<host>,<target>,auth`, which only a person's `credentials login` fixes.

Options (the job's `watch.inputs` answers): `files` (`download`, the default,
or `skip`: no attachment, pdf or video is fetched) and `timezone` (process's).

Stdlib only, no PEP 723 block: a script stage runs under the ops interpreter.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bbnotes  # noqa: E402
from door import open_ticket, post_update  # noqa: E402

BB = Path(__file__).with_name("bb.py")
COURSE_ID = re.compile(r"(_\d+_\d+)")
# A whole course with its videos; a slice's own cap ends it sooner.
CALL_TIMEOUT = 3 * 3600
EXIT_AUTH = 2


def site_and_course(target: str) -> tuple[str | None, str | None]:
    """`https://host/ultra/courses/_123_1/outline` or `https://host#_123_1` -> (`https://host`, `_123_1`)."""
    parts = urlsplit(target or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None, None
    found = COURSE_ID.search(parts.path) or COURSE_ID.search(parts.fragment)
    return f"{parts.scheme}://{parts.netloc}", (found.group(1) if found else None)


def previous_prints(items: Path) -> dict[str, str]:
    out = {}
    for cap in items.glob(f"*/{bbnotes.CAPTURE}") if items.is_dir() else []:
        try:
            out[cap.parent.name] = json.loads(cap.read_text(encoding="utf-8")).get("fingerprint")
        except (OSError, ValueError):
            continue
    return out


def main(argv: list[str]) -> int:
    ticket_id = next((a.split("=", 1)[1] for a in argv if a.startswith("ticket=")), None)
    if not ticket_id:
        print("harvest.py: needs ticket=<id>", file=sys.stderr)
        return 7
    t = open_ticket(ticket_id, stage="harvest")
    target = t.get("target") or t.get("item") or ""
    site, course = site_and_course(target)
    host = urlsplit(target).hostname or "blackboard"
    if not site or not course:
        post_update(ticket_id, "harvest", "failed", reason="the job's target names no Blackboard course url (…/courses/_N_1/…)")
        return 0
    profile, python = t.get("credential_dir"), t.get("browser_python") or sys.executable
    if not profile:
        post_update(ticket_id, "harvest", "failed", reason="no browser profile is granted to this slice: bind a `kind=dir login=browser` credential to the job")
        return 0
    capture = Path(t["capture_dir"])
    harvest, items = capture / "harvest", capture / "items"
    options = t.get("options") or {}
    argv_bb = [python, str(BB), "harvest", course, "--out", str(harvest), "--profile", profile, "--site", site]
    if str(options.get("files", "download")).lower() == "skip":
        argv_bb.append("--no-files")
    try:
        cp = subprocess.run(argv_bb, capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        post_update(ticket_id, "harvest", "failed", reason="bb.py harvest ran past its timeout", missing=[(host, target, "timeout")])
        return 0
    if cp.returncode == EXIT_AUTH:
        post_update(ticket_id, "harvest", "failed", reason="the Blackboard session expired: a person runs `credentials login` again",
                    missing=[(host, target, "auth")])
        return 0
    if cp.returncode != 0 or not (harvest / "course.json").is_file():
        # stderr is bb.py's own words, which never carry the Playwright call log or a cookie.
        tail = (cp.stderr or "").strip().splitlines()[-1:] or [f"exit {cp.returncode}"]
        post_update(ticket_id, "harvest", "failed", reason=f"bb.py harvest failed: {tail[0][:300]}", missing=[(host, target, "error")])
        return 0

    before = previous_prints(items)
    dirs = bbnotes.split(harvest, items)
    held = {k.get("resource"): k for k in t.get("known") or [] if k.get("resource")}
    captured, unchanged, moved = [], 0, 0
    for d in dirs:
        cap = json.loads((d / bbnotes.CAPTURE).read_text(encoding="utf-8"))
        cap["slug"] = t.get("slug")
        (d / bbnotes.CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        known = held.get(cap["item"])
        if known and known.get("reason") == "moved":
            moved += 1
            continue
        if known and before.get(d.name) == cap["fingerprint"] and not t.get("refresh"):
            unchanged += 1
            continue
        captured.append(d.as_posix())
    errors = json.loads((harvest / "errors.json").read_text(encoding="utf-8")) if (harvest / "errors.json").is_file() else []
    status = "partial" if errors else "ok"
    reason = f"{len(captured)} new or changed of {len(dirs)} items; {unchanged} unchanged" + (f"; {moved} moved by a person" if moved else "")
    if errors:
        reason += f"; {len(errors)} Blackboard calls failed (harvest/errors.json), a re-run fetches them"
    post_update(ticket_id, "harvest", status, reason=reason, captured=captured)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
