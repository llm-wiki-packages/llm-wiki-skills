"""The YouTube harvest stage: one video's metadata and captions through
`yt-dlp`, the capture record beside them, and the progress post — no model
session. Nothing in a harvest is left for a model to judge, so the stage
declares this as its `script`.

  llm-wiki-ops run ops/skills/channel-youtube/scripts/capture_video.py ticket=<id>

The runner starts it that way, in the stage's jail; it reads the ticket
through `tickets open`, writes into the ticket's `capture_dir` and nowhere
else, and posts `tickets update` itself. It never closes the ticket.

Steps: clear what an earlier run left (`capture.json`, `page.md`,
`written.json`: a capture dir is stable across pulls); an `item` already a
`resource` in `known[]`, with no `refresh`, is `ok` with a reason naming
`known` and fetches nothing; `yt-dlp --dump-json --no-download` into
`metadata.json` (required); `yt-dlp --skip-download --write-sub
--write-auto-sub` into `captions/` (optional); `youtube_note.py --record` for
`capture.json`. Every yt-dlp argv is a LIST with the item after `--`, so a url
carrying `&` or a quote is never a shell line. A failure is one `failed`
update: `missing=<host>,<url>,<why>`, `why` read off yt-dlp's own stderr
(`denied`, `timeout`, `auth`, else `error`).

A ticket bound to a `dir` credential (`credential_dir`, a browser profile the
slice may write) spends it as a Netscape `cookies.txt` IN that directory:
exported once through `browser_python` running `export_cookies.py` when the
jar is missing, then handed to every yt-dlp call as `--cookies <jar>`. The
profile itself is never reopened here, and nothing of it lands in the capture
dir. An export that fails is `credential_store_error` (a fresh login cannot
fix it); an `auth` wall while a jar was present deletes the jar, so the next
run after `credentials login` exports anew. Unbound, every argv is as before.

Stdlib only, deliberately no PEP 723 block: a script stage is run by the
interpreter directly, and a block is refused at install.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

OPS = "llm-wiki-ops"
STALE = ("capture.json", "page.md", "written.json")
SCHEMES = ("http", "https")
CALL_TIMEOUT = 600
# Only the proxy's own wording is `denied`, which is never retried; a 403 from YouTube is throttling or a signature change.
DENIED_MARKERS = ("tunnel connection failed", "not in the allowlist")
AUTH_MARKERS = ("sign in", "log in", "login", "age-restricted", "private video", "members-only", "members only", "confirm your age")
TIMEOUT_MARKERS = ("timed out", "timeout")
NOTE = Path(__file__).with_name("youtube_note.py")
EXPORT = Path(__file__).with_name("export_cookies.py")
JAR = "cookies.txt"


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
    argv = [*door, "--json", "pipeline", "tickets", "open", ticket]
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
    argv = [*door, "--json", "pipeline", "tickets", "update", ticket, f"stage={stage}", f"status={status}"]
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


def why_of(text: str) -> str:
    low = text.lower()
    for why, markers in (("denied", DENIED_MARKERS), ("auth", AUTH_MARKERS), ("timeout", TIMEOUT_MARKERS)):
        if any(marker in low for marker in markers):
            return why
    return "error"


def already_held(ticket: dict, item: str) -> bool:
    return any(isinstance(e, dict) and e.get("resource") == item for e in ticket.get("known") or [])


def yt_dlp(args: list[str], *, stdout_to: Path | None = None) -> tuple[int, str]:
    """One yt-dlp call, its exit code and stderr. The item is always after `--`, in the list."""
    try:
        if stdout_to is not None:
            with stdout_to.open("wb") as out:
                cp = subprocess.run(["yt-dlp", *args], stdout=out, stderr=subprocess.PIPE, timeout=CALL_TIMEOUT, check=False)
        else:
            cp = subprocess.run(["yt-dlp", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=CALL_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return 1, "timed out"
    except FileNotFoundError:
        return 1, "yt-dlp is not on PATH"
    return cp.returncode, cp.stderr.decode("utf-8", "replace")


def cookie_jar(ticket: dict) -> tuple[Path | None, str | None]:
    """The jar a bound `dir` credential is spent as, exporting it into the
    profile once. `(None, None)` unbound; `(None, error)` where the store
    cannot yield one."""
    profile = ticket.get("credential_dir")
    if not isinstance(profile, str) or not profile:
        return None, None
    jar = Path(profile) / JAR
    if jar.is_file():
        return jar, None
    python = ticket.get("browser_python")
    if not isinstance(python, str) or not python:
        return None, f"no {JAR} in the credential dir and the ticket names no browser_python to export one"
    try:
        cp = subprocess.run([python, str(EXPORT), profile, str(jar)], capture_output=True, text=True, timeout=CALL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"export_cookies.py could not run: {exc}"
    if cp.returncode != 0 or not jar.is_file():
        last = (cp.stderr.strip().splitlines() or [f"export_cookies.py exited {cp.returncode} leaving no jar"])[-1]
        return None, last[:200]
    return jar, None


def run_ticketed(ticket_id: str) -> int:
    ticket = open_ticket(ticket_id, "harvest")
    capture_rel = ticket.get("capture_dir")
    if not isinstance(capture_rel, str) or not capture_rel:
        sys.exit(f"capture_video: {ticket_id}'s ticket carries no capture_dir")
    directory = Path(capture_rel)
    directory.mkdir(parents=True, exist_ok=True)
    for name in STALE:
        (directory / name).unlink(missing_ok=True)

    item = ticket.get("item")
    if not isinstance(item, str) or not item:
        return post_update(ticket_id, "harvest", "failed", reason="no item: the ticket names no video")
    parts = urllib.parse.urlsplit(item)
    if parts.scheme.lower() not in SCHEMES or not parts.hostname:
        return post_update(ticket_id, "harvest", "failed", reason="the item is no http(s) url")
    host = parts.hostname

    if not ticket.get("refresh") and already_held(ticket, item):
        return post_update(ticket_id, "harvest", "ok", reason="known: item is already a page of this job")

    jar, store_error = cookie_jar(ticket)
    if store_error:
        # Never `auth`: a fresh login cannot fix a store that will not yield a jar.
        return post_update(ticket_id, "harvest", "failed", reason=f"credential_store_error: {store_error}", missing=[(host, item, "error")])
    cookies = ["--cookies", str(jar)] if jar else []

    metadata = directory / "metadata.json"
    code, err = yt_dlp([*cookies, "--dump-json", "--no-download", "--", item], stdout_to=metadata)
    if code != 0 or not metadata.is_file() or metadata.stat().st_size == 0:
        metadata.unlink(missing_ok=True)  # yt-dlp leaves an empty file behind a failed `>`
        why = why_of(err)
        if why == "auth" and jar:
            # The session the jar held no longer opens the venue: drop it, so the run after
            # `credentials login` exports a fresh one instead of retrying a dead jar forever.
            jar.unlink(missing_ok=True)
        detail = (err.strip().splitlines() or ["yt-dlp failed"])[-1][:200]
        return post_update(ticket_id, "harvest", "failed", reason=f"{why}: {detail}", missing=[(host, item, why)])

    # Captions are optional: a failure here is a video with none, process's question.
    yt_dlp([
        *cookies, "--skip-download", "--write-sub", "--write-auto-sub", "--sub-langs", "en", "--sub-format", "vtt/srt",
        "-o", str(directory / "captions" / "%(id)s.%(ext)s"), "--", item,
    ])

    record = subprocess.run(
        [sys.executable, str(NOTE), ".", "--capture-dir", capture_rel, "--record", "--ticket", ticket_id],
        capture_output=True, text=True,
    )
    if record.returncode != 0:
        last = (record.stderr.strip().splitlines() or ["--record refused"])[-1]
        return post_update(ticket_id, "harvest", "failed", reason=f"error: {last[:200]}")
    return post_update(ticket_id, "harvest", "ok")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("ticket_kv", metavar="ticket=<id>", help="the ticket id, as `run` invokes this script")
    args = ap.parse_args(argv)
    if not args.ticket_kv.startswith("ticket=") or len(args.ticket_kv) == len("ticket="):
        sys.exit("capture_video: pass ticket=<id>, as `run` invokes this script")
    return run_ticketed(args.ticket_kv[len("ticket="):])


if __name__ == "__main__":
    raise SystemExit(main())
