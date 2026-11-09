#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""The Blackboard harvest stage: one course, through the signed-in profile, split into one capture per item. No model session.

  llm-wiki-ops run ops/skills/channel-blackboard/scripts/harvest.py ticket=<id>

The runner starts it that way, in the stage's jail. It reads the ticket
through `tickets open`, runs `bb.py harvest` on its own interpreter (the
unit env `skills enable` built from the block above, which has Playwright)
on the granted `credential_dir` into
`<capture_dir>/harvest/`, then `bbnotes.split` into `<capture_dir>/items/`,
and posts every item directory that is new or changed since the last pull as
`captured=`. The host turns each into a transcribe ticket (a video whose
words are missing, where the job has a `transcribe` section) and a process
ticket. It never closes the ticket.

The job's target is the course's url (`https://<host>/ultra/courses/_123_1/outline`)
or `<base url>#<course id>`: the host is the site, the `_N_1` id the course.
An item is posted again when its capture's fingerprint moved or no page holds
its resource yet (`known[]`); one a person moved (`reason: moved`) is never
posted. An item `known[]` cannot list though its page was written — the
landing stamps no `ops.harvested` on a page whose file the plugin's extractor
cannot read, a slide deck — is held back on its last process step's
`written.json` while its fingerprint stands. A `course.json` naming no course
id is `failed`: every page's `resource` is built on it. Exit 2 from `bb.py` is an expired session: `failed` with
`missing=<host>,<target>,auth`, which only a person's `credentials login` fixes.

Options (the job's `watch.inputs` answers): `files` (`download`, the default,
or `skip`: no attachment, pdf or video is fetched), `discussions` (`include`,
the default, or `skip`: no board is fetched, so no classmate's name or post)
and `timezone`, the zone every date reads in. Any other `files` or
`discussions` word, or a zone this machine does not know, is `failed`.

Where pages go (`bbnotes.layout_of`): `layout` (`modules`, a folder per
top-level lesson; `flat`, one folder with module-ordered names; absent,
`legacy`, the titles a job added before 0.3.0 has), `prefix` (`position` or
`none`), `announcements_dir` and `discussions_dir` (a folder name, or
`alongside`), `depth` (`1`). The split decides each new page's place once and
keeps it in `items/placement.json`. `backfill`: `changed` (the default) posts
what is new or changed anywhere; `none` holds back the written pages of a
module whose last due date is a week past; `all` posts every item, as a
refresh does. An item a pull no longer lists is posted once, stamped
`removed`, after two whole pulls without it, and only where its page was
written; process dates the page.

A wiki customization, the portal job: a target with no course id, the site's
own courses page (`https://<host>/ultra/course`), follows every course the
signed-in student is enrolled in, one job and one ticket. Each pull lists the
enrollments, so a new term's courses join with nobody adding anything. Running
courses are pulled; a finished one (21 days past its end date) is pulled until
one clean pull has followed its end, then skipped; one with no end date whose
content has not changed for 42 days is dormant, checked weekly, and running
again once anything changes; one not started or not open is left until it is. Each
course keeps its own `harvest/<folder>` and `items/<folder>`, and its captures
carry `course_folder`, the folder under the job's `dest` that `process.py`
writes it to. `items/portal.json` remembers each course's folder and state.
`options.discover_only=true` lists and classifies and fetches no course;
`options.skip_courses`, comma-separated course ids or codes, leaves those out.
`options.subject_tags` (`PSY=psychology,LSS=study-skills`) maps a course code's
subject prefix to a tag, written once onto the course's root page, which every
page below inherits. A course's folder is its short code (`PSY2301`).

Its own code is stdlib; the block is bb.py's pin, so the browser it launches has its driver.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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
CHOICES = {"files": ("download", "skip"), "discussions": ("include", "skip")}
LIST_TIMEOUT = 600
PORTAL_LEDGER = "portal.json"
# A finished course's grades and feedback land after its last day: it is pulled for this long after that day.
FINISHED_GRACE_DAYS = 21
# A finished course whose pulls keep failing in part stops being tried after this many.
FINAL_TRIES = 3
PORTAL_PATH = re.compile(r"/ultra/courses?/?$")
# A course that states no end date is judged by its content: quiet this long, it is dormant.
QUIET_DAYS = 42
# A dormant course is still checked this often, so new content brings it back.
DORMANT_EVERY_DAYS = 7
SHORT_CODE = re.compile(r"([A-Za-z]{2,5})(\d{3,5})(?:-|$)")
TRUE_WORDS = ("true", "yes", "1")


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


def _course_record(harvest: Path) -> dict:
    try:
        found = json.loads((harvest / "course.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _written(d: Path) -> bool:
    """Whether the item's last process step wrote a page: the one record of it where `known[]` has none."""
    try:
        return bool(json.loads((d / "written.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def is_portal(target: str) -> bool:
    """A target that is the site's courses page, naming no course."""
    parts = urlsplit(target or "")
    return bool(parts.hostname) and not COURSE_ID.search(parts.path + "#" + parts.fragment) and bool(PORTAL_PATH.search(parts.path))


def _when(value) -> datetime | None:
    try:
        found = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return found if found.tzinfo else found.replace(tzinfo=timezone.utc)


def course_status(row: dict, now: datetime, grace_days: int = FINISHED_GRACE_DAYS) -> str:
    """`active`, `finished`, `upcoming` or `closed`. A course that states no dates counts as `active`: pulling too much is
    the mistake that loses nothing."""
    if row.get("organization") is True:
        return "organization"
    if str(row.get("member_available") or "").lower() == "no" or str(row.get("available") or "").lower() in ("no", "disabled"):
        return "closed"
    duration = row.get("duration") if isinstance(row.get("duration"), dict) else {}
    term = row.get("term_duration") if isinstance(row.get("term_duration"), dict) else {}
    uses_term = str(row.get("available") or "").lower() == "term" or str(duration.get("type") or "").lower() == "term"
    span = term if uses_term else duration
    start, end = _when(span.get("start")), _when(span.get("end"))
    if start and start > now:
        return "upcoming"
    if end and now > end + timedelta(days=grace_days):
        return "finished"
    return "active"


def should_pull(status: str, entry: dict, now: datetime | None = None) -> bool:
    """Whether this pull fetches a course in `status`, given what `items/portal.json` remembers of it."""
    if status == "active":
        return True
    if status == "dormant":
        last = _when(entry.get("last_pull"))
        return last is None or (now or datetime.now(timezone.utc)) - last >= timedelta(days=DORMANT_EVERY_DAYS)
    return status == "finished" and not entry.get("final_done") and int(entry.get("final_tries") or 0) < FINAL_TRIES


def quiet(entry: dict, now: datetime, days: int = QUIET_DAYS) -> bool:
    """Whether a course's content has not changed for `days`: no pull has posted a new or changed item since."""
    last = _when(entry.get("last_change"))
    return last is not None and now - last > timedelta(days=days)


def short_code(row: dict) -> str | None:
    """`PSY2301` from `PSY2301-21.01.01-2B27-S3`; None for a code that is no subject and number."""
    found = SHORT_CODE.match(str(row.get("courseId") or ""))
    return f"{found.group(1).upper()}{found.group(2)}" if found else None


def subject_map(word) -> dict[str, str]:
    """`options.subject_tags`, `PSY=psychology,LSS=study-skills`, as a map from subject prefix to tag."""
    out = {}
    for pair in str(word or "").split(","):
        prefix, _, tag = pair.partition("=")
        if prefix.strip() and tag.strip():
            out[prefix.strip().upper()] = tag.strip()
    return out


def subject_tags(row: dict, mapping: dict[str, str]) -> list[str]:
    """The subject tag a course's code maps to, as a list (empty where its prefix maps to none)."""
    code = short_code(row)
    found = SHORT_CODE.match(code) if code else None
    tag = mapping.get(found.group(1)) if found else None
    return [tag] if tag else []


def course_folder(row: dict, taken: set[str]) -> str:
    """A course's folder under the job's dest: its code as one path component, unique among the courses already placed."""
    base = short_code(row) or re.sub(r"[^A-Za-z0-9._ -]+", "-", str(row.get("courseId") or row.get("name") or row.get("id") or "course")).strip(" .-") or "course"
    name, n = base, 2
    while name.casefold() in taken:
        name, n = f"{base}-{n}", n + 1
    taken.add(name.casefold())
    return name


def pull_course(t: dict, site: str, course: str, harvest: Path, items: Path, chosen: dict, options: dict, layout: dict, profile: str,
                stamp: dict | None = None, force_course: bool = False) -> dict:
    """One course: `bb.py harvest`, the split, and which items to post. Answers `error` (`auth`, `timeout`, or `bb.py`'s words) or the counts."""
    argv_bb = [sys.executable, str(BB), "harvest", course, "--out", str(harvest), "--profile", profile, "--site", site]
    if chosen["files"] == "skip":
        argv_bb.append("--no-files")
    if chosen["discussions"] == "skip":
        argv_bb.append("--no-discussions")
    try:
        cp = subprocess.run(argv_bb, capture_output=True, text=True, timeout=CALL_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"error": "timeout", "why": "bb.py harvest ran past its timeout"}
    if cp.returncode == EXIT_AUTH:
        return {"error": "auth", "why": "the Blackboard session expired: a person runs `credentials login` again"}
    if cp.returncode != 0 or not (harvest / "course.json").is_file():
        # stderr is bb.py's own words, which never carry the Playwright call log or a cookie.
        tail = (cp.stderr or "").strip().splitlines()[-3:] or [f"exit {cp.returncode}"]
        return {"error": "error", "why": f"bb.py harvest failed: {' | '.join(line.strip() for line in tail)[:400]}"}
    if not _course_record(harvest).get("id"):
        return {"error": "error", "why": "bb.py harvest wrote a course.json naming no course id"}
    before = previous_prints(items)
    dirs = bbnotes.split(harvest, items, course_id=course, discussions=chosen["discussions"] == "include", options=options)
    held = {k.get("resource"): k for k in t.get("known") or [] if k.get("resource")}
    # `backfill=all` re-renders every page on every pull, as a refresh does.
    refresh = bool(t.get("refresh")) or layout["backfill"] == "all"
    captured, unchanged, moved, frozen, removed, listed = [], 0, 0, 0, 0, 0
    forced_unchanged = 0
    for d in dirs:
        cap = json.loads((d / bbnotes.CAPTURE).read_text(encoding="utf-8"))
        listed += not cap.get("removed")
        cap["slug"] = t.get("slug")
        cap.update(stamp or {})
        (d / bbnotes.CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        known = held.get(cap["item"])
        if known and known.get("reason") == "moved":
            moved += 1
            continue
        page = bool(known) or _written(d)
        if cap.get("removed"):
            # Gone from the course: only a page that was written has anything to date.
            if page:
                removed += 1
                captured.append(d.as_posix())
            continue
        if force_course and cap.get("kind") == "course":
            captured.append(d.as_posix())
            forced_unchanged += bool(page and before.get(d.name) == cap["fingerprint"])
            continue
        if page and cap.get("frozen") and not refresh:
            # Held back with the fingerprint last posted, so an edit made meanwhile is posted once the module thaws.
            if before.get(d.name) and before[d.name] != cap["fingerprint"]:
                cap["fingerprint"] = before[d.name]
                (d / bbnotes.CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            frozen += 1
            continue
        if page and before.get(d.name) == cap["fingerprint"] and not refresh:
            unchanged += 1
            continue
        captured.append(d.as_posix())
    errors = json.loads((harvest / "errors.json").read_text(encoding="utf-8")) if (harvest / "errors.json").is_file() else []
    # Files the site no longer has for this student (`bb.py`'s `gone.json`): named in the reason, never a reason to pull again.
    gone = json.loads((harvest / "gone.json").read_text(encoding="utf-8")) if (harvest / "gone.json").is_file() else []
    return {"error": None, "captured": captured, "changed": len(captured) - removed - forced_unchanged, "unchanged": unchanged, "moved": moved, "frozen": frozen, "removed": removed, "listed": listed, "errors": errors, "gone": len(gone)}


def write_ledger(path: Path, ledger: dict) -> None:
    """Written whole through a temporary file, so a pull that dies leaves the last one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(ledger, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def list_courses(site: str, profile: str) -> tuple[list[dict] | None, str | None]:
    """The enrollments as `bb.py courses` prints them: `(rows, None)`, or `(None, "auth")` / `(None, <why>)`."""
    try:
        cp = subprocess.run([sys.executable, str(BB), "courses", "--profile", profile, "--site", site], capture_output=True, text=True, timeout=LIST_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, "listing the courses ran past its timeout"
    if cp.returncode == EXIT_AUTH:
        return None, "auth"
    try:
        rows = json.loads(cp.stdout)
    except ValueError:
        rows = None
    if cp.returncode != 0 or not isinstance(rows, list):
        tail = (cp.stderr or "").strip().splitlines()[-1:] or [f"exit {cp.returncode}"]
        return None, f"bb.py courses failed: {tail[0][:300]}"
    return rows, None


def run_portal(t: dict, ticket_id: str, site: str, target: str, host: str, profile: str, capture: Path, chosen: dict, options: dict, layout: dict) -> int:
    """Every enrolled course that is due a pull, under one ticket."""
    rows, why = list_courses(site, profile)
    if why == "auth":
        post_update(ticket_id, "harvest", "failed", reason="the Blackboard session expired: a person runs `credentials login` again", missing=[(host, target, "auth")])
        return 0
    if rows is None:
        post_update(ticket_id, "harvest", "failed", reason=why, missing=[(host, target, "error")])
        return 0
    items_root, harvest_root = capture / "items", capture / "harvest"
    path = items_root / PORTAL_LEDGER
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ledger = {}
    known_courses = ledger.setdefault("courses", {})
    taken = {str(e.get("folder") or "").casefold() for e in known_courses.values()}
    skip = {w.strip() for w in str(options.get("skip_courses") or "").split(",") if w.strip()}
    discover = str(options.get("discover_only") or "").strip().lower() in TRUE_WORDS
    mapping = subject_map(options.get("subject_tags"))
    untagged = []
    now = datetime.now(timezone.utc)
    stamp_now = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    report, captured, new, failed, auth = [], [], [], [], False
    unchanged = removed = reused = gone = 0
    for row in rows:
        cid = row.get("id")
        if not cid or not COURSE_ID.fullmatch(str(cid)):
            continue
        status = "skipped" if {str(cid), str(row.get("courseId"))} & skip else course_status(row, now)
        entry = known_courses.get(cid)
        if entry is None and status not in ("organization", "skipped"):
            entry = known_courses[cid] = {"folder": course_folder(row, taken), "first_seen": stamp_now}
            new.append(str(row.get("name") or row.get("courseId") or cid))
            if not subject_tags(row, mapping):
                untagged.append(str(row.get("name") or cid))
        entry = entry if entry is not None else {}
        if status == "active" and quiet(entry, now):
            status = "dormant"
        if status == "active":
            entry.pop("final_done", None)
            entry.pop("final_tries", None)
        pull = should_pull(status, entry, now) and not discover
        report.append({**row, "status": status, "pull": pull, "folder": entry.get("folder")})
        entry.update({"name": row.get("name"), "code": row.get("courseId"), "status": status}) if entry else None
        if not pull or auth:
            continue
        folder = entry["folder"]
        resting = status in ("finished", "dormant")
        # The pull that first finds a course resting, or running again, says so on its root.
        ended = resting and not entry.get("marked_ended")
        reopened = status == "active" and bool(entry.get("marked_ended"))
        stamp = {"course_folder": folder, "course_current": "false" if resting else "true", "course_tags": subject_tags(row, mapping),
                 **({"course_ended": True} if ended else {}), **({"course_reopened": True} if reopened else {})}
        got = pull_course(t, site, cid, harvest_root / folder, items_root / folder, chosen, options, layout, profile,
                          stamp, force_course=ended or reopened)
        if got["error"] == "auth":
            auth = True
            continue
        if got["error"]:
            failed.append(f"{folder}: {got['why']}")
            entry["final_tries"] = int(entry.get("final_tries") or 0) + 1 if ended else 0
            continue
        captured += got["captured"]
        unchanged += got["unchanged"]
        removed += got["removed"]
        entry["last_pull"] = stamp_now
        if got["changed"] > 0 or not entry.get("last_change"):
            entry["last_change"] = stamp_now
        if ended:
            entry["marked_ended"] = True
        if reopened:
            entry.pop("marked_ended", None)
        gone += got["gone"]
        if got["errors"]:
            failed.append(f"{folder}: {len(got['errors'])} Blackboard calls failed")
        if status == "finished":
            entry["final_tries"] = int(entry.get("final_tries") or 0) + 1
            entry["final_done"] = not got["errors"]
    write_ledger(path, ledger)
    (capture / "portal-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for row in report:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    pulled = sum(1 for row in report if row["pull"])
    reason = (f"{len(report)} courses ({', '.join(f'{n} {k}' for k, n in sorted(counts.items()))}); {pulled} pulled; "
              f"{len(captured) - removed} new or changed items; {unchanged} unchanged"
              + (f"; {removed} no longer in a course" if removed else "")
              + (f"; {gone} files gone at the source (harvest/<course>/gone.json)" if gone else "")
              + (f"; new courses: {', '.join(new)}" if new else "")
              + (f"; no subject tag for: {', '.join(untagged)}" if untagged else "")
              + (f"; problems: {'; '.join(failed)}" if failed else ""))
    if auth:
        post_update(ticket_id, "harvest", "partial" if captured else "failed", reason=f"the Blackboard session expired partway: a person runs `credentials login` again; {reason}"[:1000],
                    captured=captured, missing=[(host, target, "auth")])
        return 0
    post_update(ticket_id, "harvest", "partial" if failed else "ok", reason=reason[:1000], captured=captured)
    return 0


def main(argv: list[str]) -> int:
    ticket_id = next((a.split("=", 1)[1] for a in argv if a.startswith("ticket=")), None)
    if not ticket_id:
        print("harvest.py: needs ticket=<id>", file=sys.stderr)
        return 7
    t = open_ticket(ticket_id, stage="harvest")
    target = t.get("target") or t.get("item") or ""
    site, course = site_and_course(target)
    portal = is_portal(target)
    host = urlsplit(target).hostname or "blackboard"
    if not site or not (course or portal):
        post_update(ticket_id, "harvest", "failed", reason="the job's target names no Blackboard course url (…/courses/_N_1/…) and is not the site's courses page (…/ultra/course)")
        return 0
    profile = t.get("credential_dir")
    if not profile:
        post_update(ticket_id, "harvest", "failed", reason="no browser profile is granted to this slice: bind a `kind=dir login=browser` credential to the job")
        return 0
    capture = Path(t["capture_dir"])
    harvest, items = capture / "harvest", capture / "items"
    options = t.get("options") or {}
    chosen = {key: str(options.get(key) or words[0]).strip().lower() for key, words in CHOICES.items()}
    wrong = [f"options.{key}={chosen[key]!r} (one of {', '.join(words)})" for key, words in CHOICES.items() if chosen[key] not in words]
    if wrong:
        post_update(ticket_id, "harvest", "failed", reason="; ".join(wrong))
        return 0
    try:
        bbnotes.set_zone(options.get("timezone") or None)
    except (ValueError, KeyError):
        post_update(ticket_id, "harvest", "failed", reason=f"options.timezone={options.get('timezone')!r} is no IANA zone this machine knows")
        return 0
    try:
        layout = bbnotes.layout_of(options)
    except ValueError as exc:
        post_update(ticket_id, "harvest", "failed", reason=str(exc))
        return 0
    if portal:
        return run_portal(t, ticket_id, site, target, host, profile, capture, chosen, options, layout)
    got = pull_course(t, site, course, harvest, items, chosen, options, layout, profile)
    if got["error"]:
        post_update(ticket_id, "harvest", "failed", reason=got["why"], missing=[(host, target, got["error"])])
        return 0
    captured, removed, errors = got["captured"], got["removed"], got["errors"]
    status = "partial" if errors else "ok"
    reason = (f"{len(captured) - removed} new or changed of {got['listed']} items; {got['unchanged']} unchanged" + (f"; {got['moved']} moved by a person" if got["moved"] else "")
              + (f"; {got['frozen']} in modules past their due dates (backfill=none)" if got["frozen"] else "")
              + (f"; {removed} no longer in the course" if removed else ""))
    if got["gone"]:
        reason += f"; {got['gone']} files gone at the source (harvest/gone.json)"
    if errors:
        reason += f"; {len(errors)} Blackboard calls failed (harvest/errors.json), a re-run fetches them"
    post_update(ticket_id, "harvest", status, reason=reason, captured=captured)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
