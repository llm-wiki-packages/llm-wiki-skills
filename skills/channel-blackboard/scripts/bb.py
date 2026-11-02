# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""Blackboard Learn through a signed-in browser profile: no admin-registered REST app.

The Learn REST API (`/learn/api/public/...`) answers a GET carrying the web
session's cookies, the same requests the Ultra UI sends. A person signs in
once in a headed Chromium (`login`); every later command runs headless on the
same profile and calls the API through the browser context's own request
client, so cookies, SSO redirects and TLS are the browser's.

Blackboard's `BbRouter` session cookie has no expiry, and a persistent
Chromium profile drops such cookies when it closes. So `login`, and every
command after a good call, saves the context's storage state into the profile
as `bb-state.json`, and a launch adds those cookies back before its first call.

Usage:
  bb.py login <base_url> --profile DIR [--chrome] [--timeout-min 15]
  bb.py whoami   --profile DIR
  bb.py courses  --profile DIR
  bb.py get <api-path> --profile DIR [--all]
  bb.py harvest <courseId> --out DIR --profile DIR [--no-files] [--no-discussions]

`--credential NAME` in place of `--profile` reads the directory off
`llm-wiki-ops credentials info NAME` (a `kind=dir` credential).

Exit: 0 ok; 2 not signed in, or the session expired (run `login` again);
3 usage or unreadable profile; 4 an API error that is not auth.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

API = "/learn/api/public"
OPS = "llm-wiki-ops"
STATE = "bb-state.json"
SITE = "bb-site.json"
PAGE_LIMIT = 100
PAUSE_S = 0.25
LAUNCH = {
    "args": ["--disable-blink-features=AutomationControlled"],
    "ignore_default_args": ["--enable-automation"],
}
EXIT_AUTH, EXIT_USAGE, EXIT_API = 2, 3, 4

# Handlers whose item can carry attachments; asking a folder or a link for
# them is a 4xx per item and nothing else.
# An Ultra document answers 400 to the attachments call: its files are in its body.
ATTACHABLE = ("resource/x-bb-file", "resource/x-bb-assignment", "resource/x-bb-syllabus")
MAX_NEST = 3
DOWNLOAD_TIMEOUT_MS = 300_000
SYLLABUS_HANDLER = "resource/x-bb-syllabus"
# Files an Ultra document embeds live in the body as content-collection links.
BODY_FILE_RE = re.compile(r"""(?:href|src|data-bbfile-url)\s*=\s*["']([^"']*(?:/bbcswebdav/|/xid-)[^"']*)["']""", re.I)


class AuthError(Exception):
    pass


class ApiError(Exception):
    def __init__(self, status: int, path: str, text: str = ""):
        super().__init__(f"HTTP {status} on {path}: {text[:200]}")
        self.status = status


# --- pure helpers -----------------------------------------------------------


def safe_name(text: str, limit: int = 120) -> str:
    """A title as one legal path component on every platform."""
    text = html.unescape(text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "-", text)
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return (text[:limit].rstrip(" .-")) or "untitled"


def unique(name: str, taken: set[str]) -> str:
    """`name`, or `name (2)`, `name (3)`... — two items called "Week 1" stay two."""
    stem, dot, ext = name.rpartition(".") if "." in name[1:] else (name, "", "")
    candidate, n = name, 2
    while candidate.lower() in taken:
        candidate = f"{stem} ({n}){dot}{ext}"
        n += 1
    taken.add(candidate.lower())
    return candidate


def body_file_links(body: str | None, base_url: str) -> list[str]:
    """Absolute URLs of content-collection files an item's HTML body links, in order, deduped."""
    seen, out = set(), []
    for raw in BODY_FILE_RE.findall(body or ""):
        url = urljoin(base_url + "/", html.unescape(raw))
        if urlsplit(url).hostname != urlsplit(base_url).hostname or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def is_collection_url(url: str | None, base_url: str) -> bool:
    """A link to a file in this site's own content collection, which the session can fetch."""
    if not url:
        return False
    parts = urlsplit(url)
    return parts.hostname == urlsplit(base_url).hostname and "/bbcswebdav/" in parts.path


LINK_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "kaltura.com", "panopto.com", "wistia.com", "wistia.net", "zoom.us", "loom.com")


def external_links(body: str | None, base_url: str) -> list[str]:
    """Absolute http(s) URLs a body links on hosts other than the Blackboard site, in order, deduped."""
    seen, out = set(), []
    for raw in LINK_RE.findall(body or ""):
        url = html.unescape(raw).strip()
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.hostname == urlsplit(base_url).hostname or url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def is_video_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in VIDEO_HOSTS) or bool(re.search(r"\.(mp4|m3u8|mov|webm)(\?|$)", url, re.I))


def dedupe_external(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if (r["item"], r["url"]) not in seen:
            seen.add((r["item"], r["url"]))
            out.append(r)
    return out


def filename_from(disposition: str | None, url: str) -> str:
    if disposition:
        m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", disposition) or re.search(r'filename\s*=\s*"?([^";]+)"?', disposition)
        if m:
            return safe_name(unquote(m.group(1)))
    return safe_name(unquote(urlsplit(url).path.rsplit("/", 1)[-1]) or "file")


def is_syllabus(item: dict) -> bool:
    handler = (item.get("contentHandler") or {}).get("id", "")
    return handler == SYLLABUS_HANDLER or "syllabus" in (item.get("title") or "").lower()


# --- the browser ------------------------------------------------------------


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


def resolve_profile(args) -> Path:
    if args.profile:
        return Path(args.profile).expanduser().resolve()
    proc = subprocess.run([*(front_door() or [OPS]), "--json", "credentials", "info", args.credential], capture_output=True, text=True)
    try:
        info = json.loads(proc.stdout)
    except ValueError:
        info = {}
    found = info.get("path") if isinstance(info, dict) else None
    if proc.returncode != 0 or not isinstance(found, str) or not Path(found).is_dir():
        sys.exit(f"credential {args.credential!r}: no directory ({proc.returncode}) {(proc.stderr or proc.stdout)[:300]}")
    # A profile `credentials login` minted has no bb-site.json; the dir's `host` is the site.
    args.credential_host = info.get("host") if isinstance(info.get("host"), str) else None
    return Path(found)


def read_site(profile: Path, host: str | None = None) -> str:
    try:
        return json.loads((profile / SITE).read_text())["base_url"]
    except (OSError, ValueError, KeyError):
        if host:
            return host.rstrip("/") if "://" in host else f"https://{host}"
        sys.exit(f"{profile}: no {SITE} — run `bb.py login <base_url> --profile {profile}` first")


def write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(text)


class Session:
    """One persistent-profile browser context, and the API reached through it."""

    def __init__(self, playwright, profile: Path, base_url: str, *, headed: bool = False, chrome: bool = False):
        self.profile, self.base = profile, base_url.rstrip("/")
        opts = dict(LAUNCH, headless=not headed)
        if chrome:
            opts["channel"] = "chrome"
        self.ctx = playwright.chromium.launch_persistent_context(str(profile), accept_downloads=True, **opts)
        state = profile / STATE
        if state.exists():
            try:
                cookies = json.loads(state.read_text()).get("cookies", [])
                if cookies:
                    self.ctx.add_cookies(cookies)
            except (OSError, ValueError):
                pass

    def close(self):
        self.ctx.close()

    def save_state(self):
        write_private(self.profile / STATE, json.dumps(self.ctx.storage_state()))

    def _get(self, url: str, timeout_ms: int = 60_000):
        from playwright.sync_api import Error as PlaywrightError

        try:
            return self.ctx.request.get(url, max_redirects=10, timeout=timeout_ms, fail_on_status_code=False)
        except PlaywrightError as e:
            # Its message carries the call log: every header, the session cookie among them.
            raise ApiError(0, urlsplit(url).path, str(e).splitlines()[0][:160]) from None

    def me(self) -> dict | None:
        r = self._get(f"{self.base}{API}/v1/users/me")
        return r.json() if r.status == 200 else None

    def ensure(self) -> dict:
        """The signed-in user, re-entering the site once so a live SSO session can silently renew Learn's."""
        user = self.me()
        if user is None:
            page = self.ctx.new_page()
            try:
                page.goto(f"{self.base}/ultra", wait_until="load", timeout=45_000)
                page.wait_for_timeout(3000)
            except Exception:  # noqa: BLE001 - the API answer below decides
                pass
            page.close()
            user = self.me()
        if user is None:
            raise AuthError("not signed in to Blackboard, or the session expired")
        self.save_state()
        return user

    def api(self, path: str) -> dict:
        url = path if path.startswith("http") else f"{self.base}{path if path.startswith('/') else API + '/' + path}"
        time.sleep(PAUSE_S)
        r = self._get(url)
        if r.status == 401:
            raise AuthError(f"401 on {path}")
        if r.status >= 400:
            raise ApiError(r.status, path, r.text())
        return r.json()

    def api_all(self, path: str) -> list[dict]:
        sep = "&" if "?" in path else "?"
        nxt, out = f"{path}{sep}limit={PAGE_LIMIT}", []
        while nxt:
            body = self.api(nxt)
            out.extend(body.get("results", []))
            nxt = (body.get("paging") or {}).get("nextPage")
        return out

    def download(self, url: str, dest_dir: Path, taken: set[str], name: str | None = None) -> Path:
        time.sleep(PAUSE_S)
        where = urlsplit(url).path  # the query is a signature, never logged
        try:
            r = self._get(url, DOWNLOAD_TIMEOUT_MS)
        except ApiError:  # the CDN drops a connection now and then; once more, then it counts
            time.sleep(3)
            r = self._get(url, DOWNLOAD_TIMEOUT_MS)
        if r.status == 401:
            raise AuthError(f"401 downloading {where}")
        if r.status >= 400:
            raise ApiError(r.status, where)
        if "text/html" in (r.headers.get("content-type") or "") and "/login" in r.url:
            raise AuthError(f"download landed on a login page: {where}")
        fname = unique(safe_name(name) if name else filename_from(r.headers.get("content-disposition"), r.url), taken)
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / fname
        out.write_bytes(r.body())
        return out


# --- commands ---------------------------------------------------------------


def cmd_login(pw, args) -> int:
    profile = Path(args.profile).expanduser().resolve() if args.profile else resolve_profile(args)
    profile.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip("/")
    if urlsplit(base).scheme != "https":
        sys.exit("base_url must be https://<your-blackboard-host>")
    write_private(profile / SITE, json.dumps({"base_url": base}))
    s = Session(pw, profile, base, headed=True, chrome=args.chrome)
    try:
        page = s.ctx.pages[0] if s.ctx.pages else s.ctx.new_page()
        page.goto(base, wait_until="commit")
        print(f"Sign in to {base} in the browser window (SSO / MFA as usual). Waiting up to {args.timeout_min} min...", file=sys.stderr)
        deadline = time.time() + args.timeout_min * 60
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            user = s.me()
            if user:
                page.wait_for_timeout(1500)  # let the post-login redirects settle their cookies
                s.save_state()
                print(json.dumps({"signed_in": True, "user": _user_brief(user), "profile": str(profile)}, indent=2))
                return 0
        print("timed out waiting for sign-in", file=sys.stderr)
        return EXIT_AUTH
    finally:
        s.close()


def _user_brief(u: dict) -> dict:
    name = u.get("name") or {}
    return {"id": u.get("id"), "userName": u.get("userName"), "name": " ".join(filter(None, [name.get("given"), name.get("family")]))}


def cmd_whoami(s: Session, args) -> int:
    print(json.dumps(_user_brief(s.ensure()), indent=2))
    return 0


def cmd_courses(s: Session, args) -> int:
    user = s.ensure()
    rows = []
    for m in s.api_all(f"v1/users/{user['id']}/courses?expand=course"):
        c = m.get("course") or {}
        rows.append({
            "id": m.get("courseId"),
            "courseId": c.get("courseId"),
            "name": c.get("name"),
            "role": m.get("courseRoleId"),
            "ultra": c.get("ultraStatus"),
            "term": c.get("termId"),
            "available": (c.get("availability") or {}).get("available"),
            "url": c.get("externalAccessUrl"),
        })
    print(json.dumps(rows, indent=2))
    return 0


def cmd_get(s: Session, args) -> int:
    s.ensure()
    print(json.dumps(s.api_all(args.path) if args.all else s.api(args.path), indent=2))
    return 0


def cmd_harvest(s: Session, args) -> int:
    user = s.ensure()
    cid = args.course
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    errors: list[dict] = []
    files: list[dict] = []
    external: list[dict] = []
    fetched: set[str] = set()
    taken_by_dir: dict[Path, set[str]] = {}

    def attempt(what, fn, default=None):
        try:
            return fn()
        except ApiError as e:
            errors.append({"what": what, "status": e.status, "error": str(e)})
            return default

    def dump(name, data):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2))

    def fetch(url, kind, dest: Path, owner: str, depth=0, name=None):
        """One collection file into `dest`; an HTML one has its own collection links followed."""
        if args.no_files:
            return
        url = urljoin(s.base + "/", url)
        # One signed collection file has many urls; its path is its identity.
        key = urlsplit(url).path
        if key in fetched:
            return
        fetched.add(key)
        taken = taken_by_dir.setdefault(dest, set())
        p = attempt(f"download {kind} {key}", lambda: s.download(url, dest, taken, name))
        if not p:
            return
        files.append({"item": owner, "kind": kind, "path": str(p.relative_to(out)), "src": key})
        # An Ultra document's body is a wrapper file that iframes the real page.
        if p.suffix.lower() in (".html", ".htm"):
            text = p.read_text(errors="replace")
            note_external(text, owner, str(p.relative_to(out)))
            if depth < MAX_NEST:
                for nested in body_file_links(text, s.base):
                    fetch(nested, "nested", dest, owner, depth + 1)

    def note_external(text, owner, where):
        for url in external_links(text, s.base):
            external.append({"item": owner, "where": where, "url": url, "video": is_video_url(url)})

    def scan(text, dest, owner, where):
        note_external(text or "", owner, where)
        for url in body_file_links(text, s.base):
            fetch(url, "embedded", dest, owner)

    course = None
    for v in ("v3", "v2", "v1"):
        course = attempt(f"course {v}", lambda v=v: s.api(f"{v}/courses/{cid}"))
        if course:
            break
    dump("course.json", course)

    # --- the content tree
    items: list[dict] = []

    def walk(parent: str | None, path: list[str], depth: int):
        listing = f"v1/courses/{cid}/contents" + (f"/{parent}/children" if parent else "")
        kids = attempt(f"contents {parent or 'root'}", lambda: s.api_all(listing), [])
        taken: set[str] = set()
        for k in sorted(kids, key=lambda k: k.get("position", 0)):
            k["_path"] = path + [unique(safe_name(k.get("title", "")), taken)]
            k["_parent"] = parent
            items.append(k)
            if k.get("hasChildren") and depth < 25:
                walk(k["id"], k["_path"], depth + 1)

    walk(None, [], 0)

    bodies = out / "bodies"
    bodies.mkdir(exist_ok=True)
    for it in items:
        handler = (it.get("contentHandler") or {}).get("id", "")
        ch = it.get("contentHandler") or {}
        dest = out / "files" / "/".join(it["_path"])
        if it.get("body"):
            (bodies / f"{it['id']}.html").write_text(it["body"])
        if handler in ATTACHABLE and not args.no_files:
            taken = taken_by_dir.setdefault(dest, set())
            for a in attempt(f"attachments {it['id']}", lambda it=it: s.api_all(f"v1/courses/{cid}/contents/{it['id']}/attachments"), []):
                url = f"{s.base}{API}/v1/courses/{cid}/contents/{it['id']}/attachments/{a['id']}/download"
                p = attempt(f"download attachment {a['id']}", lambda url=url, a=a, taken=taken: s.download(url, dest, taken, a.get("fileName")))
                if p:
                    files.append({"item": it["id"], "kind": "attachment", "path": str(p.relative_to(out)), "mime": a.get("mimeType")})
        if ch.get("url"):
            link = urljoin(s.base + "/", ch["url"])
            if is_collection_url(link, s.base):
                fetch(link, "linked", dest, it["id"])
            elif urlsplit(link).hostname != urlsplit(s.base).hostname:
                external.append({"item": it["id"], "where": "contentHandler.url", "url": link, "video": is_video_url(link), "title": it.get("title")})
        scan((it.get("body") or "") + (ch.get("instructions") or ""), dest, it["id"], f"item {it['id']}")

    # --- announcements, calendar
    announcements = attempt("announcements", lambda: s.api_all(f"v1/courses/{cid}/announcements"), [])
    dump("announcements.json", announcements)
    for a in announcements:
        scan(a.get("body"), out / "files" / "_announcements" / safe_name(a.get("title", "")), a.get("id"), f"announcement {a.get('id')}")
    dump("calendar.json", attempt("calendar", lambda: s.api_all(f"v1/calendars/items?courseId={cid}"), []))

    # --- discussions: every board's topic and every post the student can see
    # `--no-discussions`: classmates' names and posts are never fetched, so nothing downstream can carry them.
    discussions = [] if args.no_discussions else attempt("discussions", lambda: s.api_all(f"v1/courses/{cid}/discussions"), [])
    dump("discussions.json", discussions)
    posts = 0
    for d in discussions:
        dest = out / "files" / "_discussions" / safe_name(d.get("title", ""))
        scan(json.dumps(d.get("topic")) if not isinstance(d.get("topic"), str) else d["topic"], dest, d["id"], f"discussion {d['id']}")
        msgs = attempt(f"discussion messages {d['id']}", lambda d=d: s.api_all(f"v1/courses/{cid}/discussions/{d['id']}/messages"), [])
        posts += len(msgs)
        dump(f"discussions/{d['id']}.json", msgs)
        for m in msgs:
            scan(m.get("body"), dest, m.get("id"), f"post {m.get('id')}")

    # --- the gradebook: columns, the student's own grades, attempts and submitted files
    columns = attempt("gradebook columns", lambda: s.api_all(f"v2/courses/{cid}/gradebook/columns"), [])
    dump("gradebook-columns.json", columns)
    dump("my-grades.json", attempt("my grades", lambda: s.api_all(f"v2/courses/{cid}/gradebook/users/{user['id']}"), []))
    attempts = []
    for col in columns:
        for a in attempt(f"attempts {col['id']}", lambda col=col: s.api_all(f"v2/courses/{cid}/gradebook/columns/{col['id']}/attempts"), []):
            # The public attempt omits the submitted files; Ultra's own call carries them.
            detail = attempt(f"attempt detail {a['id']}", lambda a=a: s.api(f"/learn/api/v1/courses/{cid}/gradebook/attempts/{a['id']}"))
            a["_column"] = col.get("name")
            attempts.append(a)
            dump(f"attempts/{a['id']}.json", detail)
            dest = out / "files" / "_submissions" / safe_name(col.get("name", ""))
            scan(a.get("studentSubmission"), dest, a["id"], f"attempt {a['id']}")
            scan(a.get("feedback"), dest, a["id"], f"attempt feedback {a['id']}")
            for f in (detail or {}).get("studentSubmissionFiles") or []:
                url = (f.get("file") or {}).get("permanentUrl")
                if url:
                    fetch(url, "submission", dest, a["id"], name=(f.get("file") or {}).get("fileName") or f.get("name"))
    dump("attempts.json", attempts)

    flat = [{
        "id": it.get("id"),
        "parent": it["_parent"],
        "path": "/".join(it["_path"]),
        "title": it.get("title"),
        "handler": (it.get("contentHandler") or {}).get("id"),
        "url": (it.get("contentHandler") or {}).get("url"),
        "created": it.get("created"),
        "modified": it.get("modified"),
        "available": (it.get("availability") or {}).get("available"),
        "has_body": bool(it.get("body")),
        "syllabus": is_syllabus(it),
        "raw": {k: v for k, v in it.items() if not k.startswith("_") and k != "body"},
    } for it in items]
    dump("contents.json", flat)
    dump("files.json", files)
    dump("external.json", dedupe_external(external))
    dump("errors.json", errors)
    summary = {
        "course": {"id": cid, "courseId": (course or {}).get("courseId"), "name": (course or {}).get("name")},
        "items": len(flat),
        "handlers": _count(f["handler"] for f in flat),
        "syllabus": [f["path"] for f in flat if f["syllabus"]],
        "files": len(files),
        "file_kinds": _count(f["kind"] for f in files),
        "announcements": len(announcements),
        "discussions": len(discussions),
        "posts": posts,
        "gradebook_columns": len(columns),
        "attempts": len(attempts),
        "external_links": len(dedupe_external(external)),
        "external_videos": sorted({e["url"] for e in external if e["video"]}),
        "errors": len(errors),
    }
    dump("summary.json", summary)
    s.save_state()
    print(json.dumps(summary, indent=2))
    return 0


def _count(values) -> dict:
    out: dict = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bb.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        g = p.add_mutually_exclusive_group(required=True)
        g.add_argument("--profile", help="the browser profile directory")
        g.add_argument("--credential", help="a kind=dir credential whose directory is the profile")
        p.add_argument("--chrome", action="store_true", help="real Chrome instead of bundled Chromium")
        p.add_argument("--headed", action="store_true")
        p.add_argument("--site", help="the site's base url, over the profile's bb-site.json (a job's target names it)")
        return p

    p = common(sub.add_parser("login", help="headed sign-in; saves the session"))
    p.add_argument("base_url")
    p.add_argument("--timeout-min", type=int, default=15)
    common(sub.add_parser("whoami"))
    common(sub.add_parser("courses"))
    p = common(sub.add_parser("get", help="one raw API GET, e.g. v1/users/me"))
    p.add_argument("path")
    p.add_argument("--all", action="store_true", help="follow paging.nextPage")
    p = common(sub.add_parser("harvest", help="a course's content tree, bodies, files, announcements, gradebook columns"))
    p.add_argument("course", help="the course's primary id (_123_1), from `courses`")
    p.add_argument("--out", required=True)
    p.add_argument("--no-files", action="store_true")
    p.add_argument("--no-discussions", action="store_true", help="fetch no discussion board, so no classmate's name or post")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        if args.cmd == "login":
            return cmd_login(pw, args)
        profile = resolve_profile(args)
        site = args.site.rstrip("/") if args.site else read_site(profile, getattr(args, "credential_host", None))
        s = Session(pw, profile, site, headed=args.headed, chrome=args.chrome)
        try:
            return {"whoami": cmd_whoami, "courses": cmd_courses, "get": cmd_get, "harvest": cmd_harvest}[args.cmd](s, args)
        except AuthError as e:
            print(f"auth: {e} — run `bb.py login <base_url> --profile {profile}` again", file=sys.stderr)
            return EXIT_AUTH
        except ApiError as e:
            print(f"api: {e}", file=sys.stderr)
            return EXIT_API
        finally:
            s.close()


if __name__ == "__main__":
    sys.exit(main())
