"""The YouTube harvest stage: one video's metadata and captions through
`yt-dlp`, the capture record beside them, and the progress post — no model
session. Nothing in a harvest is left for a model to judge, so the stage
declares this as its `script`.

  llm-wiki-ops run ops/skills/channel-youtube/scripts/capture_video.py ticket=<id>

The runner starts it that way, in the stage's jail; it reads the ticket
through `tickets open`, writes into the ticket's `capture_dir` and nowhere
else, and posts `tickets update` itself. It never closes the ticket.

Steps: clear what an earlier run left (`capture.json`, `page.md`,
`written.json` and `enrich/`: a capture dir is stable across pulls); an `item` already a
`resource` in `known[]`, with no `refresh`, is `ok` with a reason naming
`known` and fetches nothing; `yt-dlp --dump-json --no-download` into
`metadata.json` (required); `yt-dlp --skip-download --write-sub
--write-auto-sub` into `captions/` (optional); `youtube_note.py --record` for
`capture.json`. Every yt-dlp argv is a LIST with the item after `--`, so a url
carrying `&` or a quote is never a shell line. A failure is one `failed`
update: `missing=<host>,<url>,<why>`, `why` read off yt-dlp's own stderr
(`denied`, `timeout`, `auth`, else `error`).

A ticket bound to a `dir` credential (`credential_dir`, granted read-write)
spends its saved browser state as a Netscape `cookies.txt` IN that
directory: written fresh each run from `credentials browser-state get`, the
YouTube, Google and media-CDN cookies only, and handed to every yt-dlp call
as `--cookies <jar>`. yt-dlp writes the cookies YouTube rotates back into the
jar, and the run merges them into the state with `credentials browser-state
put` once the calls are done, so the state stays the live session for a run
that comes after a `credentials login` too. No browser opens here: YouTube
rotates a session under any open tab, so a jar never shares one. A jar
newer than the state is a killed run's rotation, saved before the new jar is
written. A state that does not answer or holds no YouTube cookie is
`credential_store_error`. Nothing of the directory lands in the capture
dir. Unbound, every argv is as before.

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
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
# YouTube's IP-reputation wall carries the words "sign in" too, but a logged-in jar hits it as well: throttling, not an auth wall.
BOT_CHECK_MARKERS = ("not a bot",)
NOTE = Path(__file__).with_name("youtube_note.py")
# yt-dlp's cookie file, in the credential directory: never in the capture dir.
JAR = "cookies.txt"
JAR_HEADER = "# Netscape HTTP Cookie File\n"
# curl's and yt-dlp's marker for an HttpOnly cookie's line.
HTTPONLY = "#HttpOnly_"
# The cookies the jar carries: YouTube's, Google's account cookies and the media CDN's.
DOMAINS = ("youtube.com", "google.com", "googlevideo.com")


class StoreError(Exception):
    """The credential's store would not yield or keep a jar: never `auth`, since no fresh login fixes it."""


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


def wanted(domain: str) -> bool:
    host = domain.lstrip(".").lower()
    return any(host == d or host.endswith("." + d) for d in DOMAINS)


def _key(cookie: dict) -> tuple:
    return (cookie.get("name"), cookie.get("domain"), cookie.get("path"))


def netscape_line(cookie: dict) -> str:
    domain = cookie["domain"]
    expires = cookie.get("expires", -1)
    expiry = 0 if expires is None or expires < 0 else int(expires)
    return "\t".join([
        (HTTPONLY if cookie.get("httpOnly") else "") + domain,
        "TRUE" if domain.startswith(".") else "FALSE",
        cookie.get("path") or "/",
        "TRUE" if cookie.get("secure") else "FALSE",
        str(expiry),
        cookie["name"],
        cookie.get("value", ""),
    ])


def write_jar(jar: Path, cookies: list[dict]) -> None:
    """The cookies as a Netscape file, 0600, written whole through a temp file then renamed."""
    body = JAR_HEADER + "".join(netscape_line(c) + "\n" for c in cookies)
    fd, tmp = tempfile.mkstemp(prefix=".cookies-", suffix=".tmp", dir=str(jar.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        os.chmod(tmp, 0o600)
        os.replace(tmp, jar)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_jar(jar: Path, saved: dict) -> list[dict]:
    """The jar's cookies as browser-state cookies, each over the saved one of its key, so what a Netscape line cannot
    carry (`sameSite`) is kept. yt-dlp writes no `#HttpOnly_` marker back, so a line without one keeps the saved
    `httpOnly`; a new cookie without one is not HttpOnly."""
    cookies = []
    for line in jar.read_text(encoding="utf-8").splitlines():
        if line.startswith(HTTPONLY):
            line, http_only = line[len(HTTPONLY):], True
        elif not line.strip() or line.startswith("#"):
            continue
        else:
            http_only = False
        fields = line.split("\t")
        if len(fields) != 7:
            continue
        domain, _, path, secure, expiry, name, value = fields
        found = {"name": name, "value": value, "domain": domain, "path": path,
                 "expires": float(expiry) if expiry.isdigit() and int(expiry) > 0 else -1, "secure": secure == "TRUE"}
        cookie = {"httpOnly": False, **saved.get(_key(found), {}), **found}
        if http_only:
            cookie["httpOnly"] = True
        cookies.append(cookie)
    return cookies


def state_verb(verb: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    """`credentials browser-state <verb>` through the front door; inside the slice it finds the credential from the
    run's slot, never by name."""
    try:
        return subprocess.run([*front_door(), "--json", "credentials", "browser-state", verb], input=stdin,
                              capture_output=True, text=True, timeout=CALL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StoreError(f"credentials browser-state {verb} did not run: {exc}") from None


def keep_rotation(jar: Path, saved: dict) -> None:
    """`save_jar` after the yt-dlp calls. A save that does not land fails nothing: the jar stays newer than the state,
    and the next run saves it first."""
    try:
        save_jar(jar, saved)
    except (StoreError, OSError) as exc:
        print(f"capture_video: the rotated cookies were not saved back ({exc}); the next run saves them", file=sys.stderr)


def browser_state() -> tuple[dict, Path | None]:
    """The credential's saved browser state and its file, through `credentials browser-state get`; raises
    `StoreError` where the verb does not answer one."""
    cp = state_verb("get")
    try:
        answer = json.loads(cp.stdout)
    except ValueError:
        answer = None
    if cp.returncode != 0 or not isinstance(answer, dict) or not isinstance(answer.get("state"), dict):
        said = (cp.stderr or cp.stdout or "").strip().splitlines() or [f"exited {cp.returncode}"]
        raise StoreError(f"credentials browser-state get: {said[-1][:200]}")
    where = answer.get("path")
    return answer["state"], Path(where) if isinstance(where, str) and where else None


def save_jar(jar: Path, saved: dict) -> None:
    """The jar's cookies merged back into the credential's state, through `credentials browser-state put`: yt-dlp
    writes the cookies YouTube rotates into the jar, and the state is where the next run reads them from."""
    cp = state_verb("put", stdin=json.dumps({"cookies": read_jar(jar, saved), "origins": []}))
    if cp.returncode != 0:
        said = (cp.stderr or cp.stdout or "").strip().splitlines() or [f"exited {cp.returncode}"]
        raise StoreError(f"credentials browser-state put: {said[-1][:200]}")


def newer(jar: Path, state: Path | None) -> bool:
    return jar.is_file() and (state is None or not state.is_file() or jar.stat().st_mtime_ns > state.stat().st_mtime_ns)


def cookie_jar(ticket: dict) -> tuple[Path | None, dict]:
    """The jar a bound `dir` credential is spent as, written fresh from the credential's browser state, and the saved
    cookies by key. A jar newer than the state is a run's rotation that was never saved back (the run was killed
    first): it is saved before the new one is written. `(None, {})` unbound; raises `StoreError` where the store
    cannot yield one."""
    profile = ticket.get("credential_dir")
    if not isinstance(profile, str) or not profile:
        return None, {}
    jar = Path(profile) / JAR
    state, where = browser_state()
    saved = {_key(c): c for c in state.get("cookies") or [] if isinstance(c, dict)}
    try:
        good = False
        if jar.is_file():
            with jar.open("rb") as handle:
                good = handle.readline().startswith(b"# Netscape")
        if good and newer(jar, where):
            save_jar(jar, saved)
            state, where = browser_state()
            saved = {_key(c): c for c in state.get("cookies") or [] if isinstance(c, dict)}
        cookies = [c for c in saved.values() if wanted(c.get("domain", ""))]
        if not cookies:
            raise StoreError(f"the credential holds no cookies for {', '.join(DOMAINS)}: not logged in to youtube.com")
        write_jar(jar, cookies)
    except OSError as exc:
        # The dir is granted read-write to this slice; a dir that cannot be read is the store's problem, not a login's.
        raise StoreError(f"credential dir cannot be read or written: {exc}") from None
    return jar, saved


def run_ticketed(ticket_id: str) -> int:
    ticket = open_ticket(ticket_id, "harvest")
    capture_rel = ticket.get("capture_dir")
    if not isinstance(capture_rel, str) or not capture_rel:
        sys.exit(f"capture_video: {ticket_id}'s ticket carries no capture_dir")
    directory = Path(capture_rel)
    directory.mkdir(parents=True, exist_ok=True)
    for name in STALE:
        (directory / name).unlink(missing_ok=True)
    # An enrich unit's notes were made from the bytes this pull replaces.
    enrich = directory / "enrich"
    if enrich.is_symlink():
        enrich.unlink()
    else:
        shutil.rmtree(enrich, ignore_errors=True)

    item = ticket.get("item")
    if not isinstance(item, str) or not item:
        return post_update(ticket_id, "harvest", "failed", reason="no item: the ticket names no video")
    parts = urllib.parse.urlsplit(item)
    if parts.scheme.lower() not in SCHEMES or not parts.hostname:
        return post_update(ticket_id, "harvest", "failed", reason="the item is no http(s) url")
    host = parts.hostname

    if not ticket.get("refresh") and already_held(ticket, item):
        return post_update(ticket_id, "harvest", "ok", reason="known: item is already a page of this job")

    try:
        jar, saved = cookie_jar(ticket)
    except StoreError as exc:
        # Never `auth`: a fresh login cannot fix a store that will not yield a jar.
        return post_update(ticket_id, "harvest", "failed", reason=f"credential_store_error: {exc}", missing=[(host, item, "error")])
    try:
        return fetch(ticket_id, capture_rel, directory, item, host, jar)
    finally:
        if jar is not None:
            keep_rotation(jar, saved)


def fetch(ticket_id: str, capture_rel: str, directory: Path, item: str, host: str, jar: Path | None) -> int:
    """yt-dlp's two calls and the capture record, and the update that says how they went."""
    cookies = ["--cookies", str(jar)] if jar else []

    metadata = directory / "metadata.json"
    code, err = yt_dlp([*cookies, "--dump-json", "--no-download", "--", item], stdout_to=metadata)
    if code != 0 or not metadata.is_file() or metadata.stat().st_size == 0:
        metadata.unlink(missing_ok=True)  # yt-dlp leaves an empty file behind a failed `>`
        why = why_of(err)
        if why == "auth" and jar and any(marker in err.lower() for marker in BOT_CHECK_MARKERS):
            # A bot check with a live jar is throttling: retryable, and no login fixes it.
            why = "error"
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
