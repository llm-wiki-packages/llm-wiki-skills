# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""Blackboard Learn through a signed-in browser session: no admin-registered REST app.

The Learn REST API (`/learn/api/public/...`) answers a GET carrying the web
session's cookies, the same requests the Ultra UI sends. A person signs in
once with `llm-wiki-ops credentials login <credential>`; every command here
runs headless through the plugin's launcher (`llm_wiki_browser`), which seeds
the context from that credential's saved browser state and saves it back, and
calls the API through the context's own request client, so cookies, SSO
redirects and TLS are the browser's.

Usage:
  bb.py whoami   [--credential NAME] [--site URL]
  bb.py courses  [--credential NAME] [--site URL]
  bb.py get <api-path> [--all] [--credential NAME] [--site URL]
  bb.py harvest <courseId> --out DIR [--no-files] [--no-discussions] [--credential NAME] [--site URL]

The credential is the run's `dir` slot (`LLM_WIKI_SLOT_DIR`), as a job's
harvest hands it. `--credential NAME` names one where the run was handed
none: its directory off `llm-wiki-ops credentials info NAME`, and its `host`
the site unless `--site` says otherwise.

Exit: 0 ok; 2 not signed in, or the session expired (run `credentials login`
again); 3 usage, or no credential; 4 an API error that is not auth; 5 the
browser state could not be saved back to the credential.
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
from urllib.parse import quote, unquote, urljoin, urlsplit

API = "/learn/api/public"
OPS = "llm-wiki-ops"
# The run's `dir` slot, which the plugin's launcher and `credentials browser-state` read.
SLOT_DIR_ENV = "LLM_WIKI_SLOT_DIR"
PAGE_LIMIT = 100
PAUSE_S = 0.25
EXIT_AUTH, EXIT_USAGE, EXIT_API, EXIT_STORE = 2, 3, 4, 5

# Handlers whose item can carry attachments; asking a folder or a link for
# them is a 4xx per item and nothing else.
# An Ultra document answers 400 to the attachments call: its files are in its body.
ATTACHABLE = ("resource/x-bb-file", "resource/x-bb-assignment", "resource/x-bb-syllabus")
MAX_NEST = 3
DOWNLOAD_TIMEOUT_MS = 300_000
# A file the site answers with one of these is not there for this student: a re-run cannot fetch it, so it is gone, not failed.
GONE_STATUSES = (403, 404, 410)
# A busy or failing site, worth asking again within the run; the waits between the tries, in seconds.
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRY_WAITS_S = (3, 10)
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


def read_json(path: Path, default):
    """A JSON file a previous pull wrote, or `default` where it is absent, unreadable or the wrong shape."""
    try:
        found = json.loads(path.read_text())
    except (OSError, ValueError):
        return default
    return found if isinstance(found, type(default)) else default


def reusable(row: dict | None, owner, out: Path, dest: Path, prior_modified: dict, now_modified: dict) -> Path | None:
    """The file `row` names, kept from the last pull: on disk, still in the folder this pull files it under, and owned by
    something unchanged. A content item says so by `modified`; an announcement, post or attempt has no such date here, so its
    file's own collection path stands as its identity."""
    if not row or not row.get("path"):
        return None
    found = out / row["path"]
    if not found.is_file() or found.parent != dest:
        return None
    if owner in now_modified and prior_modified.get(owner) != now_modified[owner]:
        return None
    return found


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


def as_site(host: str) -> str:
    host = host.rstrip("/")
    return host if "://" in host else f"https://{host}"


def resolve_credential(args) -> str | None:
    """The site the named credential's `host` gives, after pointing this run's slot at its directory; None with no name.

    A run a job or `run credential=` handed its slot keeps that one: a name beside it is refused, as the plugin's
    `credentials browser-state` refuses one."""
    if os.environ.get(SLOT_DIR_ENV):
        if args.credential:
            print(f"this run was handed its credential as {SLOT_DIR_ENV}: drop --credential", file=sys.stderr)
            sys.exit(EXIT_USAGE)
        return None
    if not args.credential:
        print("no credential: run under a job, or pass --credential NAME (a `kind=dir login=browser` credential)", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    proc = subprocess.run([*(front_door() or [OPS]), "--json", "credentials", "info", args.credential], capture_output=True, text=True)
    try:
        info = json.loads(proc.stdout)
    except ValueError:
        info = {}
    found = info.get("path") if isinstance(info, dict) else None
    if proc.returncode != 0 or not isinstance(found, str) or not Path(found).is_dir():
        print(f"credential {args.credential!r}: no directory ({proc.returncode}) {(proc.stderr or proc.stdout)[:300]}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    # The launcher and the state verb it saves through both find the credential here.
    os.environ[SLOT_DIR_ENV] = found
    host = info.get("host")
    return as_site(host) if isinstance(host, str) and host else None


SSO_LINK = re.compile(r'href="(/auth-saml/saml/login\?apId=(_\d+_\d+)[^"]*)"')
PASSWORD_FIELD = re.compile(r'<input[^>]+type=["\']?password', re.I)
# The renewal's budget: each navigation answers within RENEW_GOTO_MS, the sign-in page shows within
# RENEW_POLLS * RENEW_POLL_MS, and the provider sends the browser back within RENEW_RETURN_MS.
RENEW_GOTO_MS, RENEW_POLLS, RENEW_POLL_MS, RENEW_RETURN_MS = 30_000, 15, 2_000, 30_000


def _first_line(e: Exception) -> str:
    """An error's first line, short: a Playwright message's later lines carry the call log, cookies among them."""
    return (str(e).splitlines() or [type(e).__name__])[0][:160]


def sso_link(html: str, base: str, provider: str | None) -> str | None:
    """The sign-in page's SAML link to follow: the named provider's (`_4405_1`), else the page's only one; None when
    the page has none, or several and none is named. The link always returns to `<base>/ultra`."""
    ids = list(dict.fromkeys(m.group(2) for m in SSO_LINK.finditer(html)))
    pick = provider if provider in ids else (ids[0] if provider is None and len(ids) == 1 else None)
    if pick is None:
        return None
    return f"{base}/auth-saml/saml/login?apId={pick}&redirectUrl={quote(base + '/ultra', safe='')}"


class Session:
    """One browser context the plugin's launcher opened, and the API reached through it."""

    def __init__(self, ctx, base_url: str, sso: str | None = None):
        self.ctx, self.base, self.sso = ctx, base_url.rstrip("/"), sso

    def save_state(self):
        import llm_wiki_browser

        llm_wiki_browser.save_state(self.ctx)

    def _get(self, url: str, timeout_ms: int = 60_000):
        from playwright.sync_api import Error as PlaywrightError

        try:
            return self.ctx.request.get(url, max_redirects=10, timeout=timeout_ms, fail_on_status_code=False)
        except PlaywrightError as e:
            # Its message carries the call log: every header, the session cookie among them.
            raise ApiError(0, urlsplit(url).path, str(e).splitlines()[0][:160]) from None

    def _get_retrying(self, url: str, timeout_ms: int = 60_000):
        """`_get`, asked again after a dropped connection or a busy-site status, `RETRY_WAITS_S` apart: the last answer, or
        the last connection error once the tries are spent."""
        for wait in (*RETRY_WAITS_S, None):
            try:
                r = self._get(url, timeout_ms)
            except ApiError:
                if wait is None:
                    raise
                time.sleep(wait)
                continue
            if r.status not in RETRY_STATUSES or wait is None:
                return r
            time.sleep(wait)
        raise AssertionError("unreachable")

    def me(self) -> dict | None:
        r = self._get(f"{self.base}{API}/v1/users/me")
        return r.json() if r.status == 200 else None

    def ensure(self) -> dict:
        """The signed-in user, re-entering the site once so a live SSO session can silently renew Learn's.

        A site whose `/ultra` lands on Learn's own sign-in page (a button per identity provider, no redirect) is
        renewed through that page's SAML link: `--sso <apId>` names the provider, or the page's only link is taken.
        A live identity-provider session then signs Learn in with no prompt.

        No step waits for a page's `load` event: that waits on every third-party host the page pulls in, and one a
        firewall holds for approval stalls it. Signed out (`AuthError`) is only what the site or the provider said: a
        sign-in page with no usable link, or the provider keeping the browser to ask for a password. A page that never
        arrived is a network failure (`ApiError`), which a keepalive records as an error, not a sign-out (skills #137).
        """
        user = self.me()
        if user is None:
            page = self.ctx.new_page()
            try:
                user, stalled = self._renew(page)
            finally:
                page.close()
            if user is None:
                user = self.me()
            if user is None and stalled:
                raise ApiError(0, "/ultra", f"the sign-in did not finish loading: {stalled}")
        if user is None:
            raise AuthError("not signed in to Blackboard, or the session expired")
        self.save_state()
        return user

    def _renew(self, page) -> tuple[dict | None, str | None]:
        """One pass through the site's sign-in: `(user, None)` once signed in, `(None, None)` where the site or the
        provider says signed out, `(None, why)` where a page never arrived."""
        try:
            page.goto(f"{self.base}/ultra", wait_until="commit", timeout=RENEW_GOTO_MS)
        except Exception as e:  # noqa: BLE001 - a navigation that never answered
            return None, _first_line(e)
        html_now = ""
        for _ in range(RENEW_POLLS):
            user = self.me()
            if user is not None:
                return user, None
            try:
                html_now = page.content()
            except Exception:  # noqa: BLE001 - mid-navigation; read it on the next poll
                html_now = ""
            if SSO_LINK.search(html_now) or PASSWORD_FIELD.search(html_now):
                break
            page.wait_for_timeout(RENEW_POLL_MS)
        else:
            return None, "the sign-in page never showed a sign-in"
        link = sso_link(html_now, self.base, self.sso)
        if not link:
            return None, None
        try:
            page.goto(link, wait_until="commit", timeout=RENEW_GOTO_MS)
        except Exception as e:  # noqa: BLE001
            return None, _first_line(e)
        try:
            page.wait_for_url(f"{self.base}/ultra**", wait_until="commit", timeout=RENEW_RETURN_MS)
        except Exception as e:  # noqa: BLE001 - where the browser waits now decides
            at = urlsplit(page.url or "")
            if at.scheme.startswith("http") and at.netloc != urlsplit(self.base).netloc:
                return None, None
            return None, _first_line(e)
        page.wait_for_timeout(3000)
        return self.me(), None

    def api(self, path: str) -> dict:
        url = path if path.startswith("http") else f"{self.base}{path if path.startswith('/') else API + '/' + path}"
        time.sleep(PAUSE_S)
        r = self._get_retrying(url)
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
        # The CDN drops a connection now and then, and a busy site answers 429 or 5xx: asked again before it counts.
        r = self._get_retrying(url, DOWNLOAD_TIMEOUT_MS)
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


def _user_brief(u: dict) -> dict:
    name = u.get("name") or {}
    return {"id": u.get("id"), "userName": u.get("userName"), "name": " ".join(filter(None, [name.get("given"), name.get("family")]))}


def cmd_whoami(s: Session, args) -> int:
    print(json.dumps(_user_brief(s.ensure()), indent=2))
    return 0


def cmd_courses(s: Session, args) -> int:
    user = s.ensure()
    rows = []
    terms: dict[str, dict | None] = {}

    def term_dates(term_id):
        """The term's own dates, which a course set to "use the term" has in place of its own; None where a student may not read it."""
        if not term_id:
            return None
        if term_id not in terms:
            try:
                terms[term_id] = (s.api(f"v1/terms/{term_id}").get("availability") or {}).get("duration")
            except ApiError:
                terms[term_id] = None
        return terms[term_id]

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
            # What the portal job reads to tell a running course from a finished one.
            "member_available": (m.get("availability") or {}).get("available"),
            "duration": (c.get("availability") or {}).get("duration"),
            "term_duration": term_dates(c.get("termId")),
            "organization": c.get("organization"),
            "created": c.get("created"),
            "last_accessed": m.get("lastAccessed"),
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
    # What the last pull into this directory left: a file is fetched again only where something says it may have changed.
    prior_files = read_json(out / "files.json", [])
    prior_modified = {r.get("id"): r.get("modified") for r in read_json(out / "contents.json", []) if isinstance(r, dict) and r.get("id")}
    by_src = {r["src"]: r for r in prior_files if isinstance(r, dict) and r.get("src")}
    by_attachment = {(r.get("item"), r.get("attachment")): r for r in prior_files if isinstance(r, dict) and r.get("attachment")}
    now_modified: dict[str, str | None] = {}
    reused = [0]
    # Files the site no longer has for this student, by collection path or attachment: skipped while their owner is unchanged.
    gone: list[dict] = []
    prior_gone = [r for r in read_json(out / "gone.json", []) if isinstance(r, dict)]
    gone_by_src = {r["src"]: r for r in prior_gone if r.get("src")}
    gone_by_attachment = {(r.get("item"), r.get("attachment")): r for r in prior_gone if r.get("attachment")}
    today = time.strftime("%Y-%m-%d", time.gmtime())

    def still_gone(row: dict | None, owner) -> bool:
        """A file an earlier pull found gone, whose owner has not changed since: not asked for again. An owner that changed
        (an instructor who edited the announcement may have fixed it) is asked again."""
        if not row:
            return False
        if owner in now_modified and prior_modified.get(owner) != now_modified[owner]:
            return False
        gone.append(row)
        return True

    def download(what, fn, row: dict):
        """`fn()`'s file; None where it failed (an error, which a re-run retries) or is gone (recorded, never an error)."""
        try:
            return fn()
        except ApiError as e:
            if e.status in GONE_STATUSES:
                gone.append({**row, "status": e.status, "since": today})
            else:
                errors.append({"what": what, "status": e.status, "error": str(e)})
            return None

    def kept(row: dict | None, owner, dest: Path) -> Path | None:
        """The file a previous pull left for `row`, where its owner has not changed since; None means fetch it."""
        found = reusable(row, owner, out, dest, prior_modified, now_modified)
        if found:
            reused[0] += 1
            taken_by_dir.setdefault(dest, set()).add(found.name.lower())
        return found

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
        if still_gone(gone_by_src.get(key), owner):
            return
        p = kept(by_src.get(key), owner, dest) or download(
            f"download {kind} {key}", lambda: s.download(url, dest, taken, name), {"item": owner, "kind": kind, "src": key})
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
    now_modified.update({it.get("id"): it.get("modified") for it in items})

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
                if still_gone(gone_by_attachment.get((it["id"], a["id"])), it["id"]):
                    continue
                p = kept(by_attachment.get((it["id"], a["id"])), it["id"], dest) or download(
                    f"download attachment {a['id']}", lambda url=url, a=a, taken=taken: s.download(url, dest, taken, a.get("fileName")),
                    {"item": it["id"], "kind": "attachment", "attachment": a["id"], "name": a.get("fileName")})
                if p:
                    files.append({"item": it["id"], "kind": "attachment", "attachment": a["id"], "path": str(p.relative_to(out)), "mime": a.get("mimeType")})
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
    dump("gone.json", gone)
    summary = {
        "course": {"id": cid, "courseId": (course or {}).get("courseId"), "name": (course or {}).get("name")},
        "items": len(flat),
        "handlers": _count(f["handler"] for f in flat),
        "syllabus": [f["path"] for f in flat if f["syllabus"]],
        "files": len(files),
        "files_reused": reused[0],
        "file_kinds": _count(f["kind"] for f in files),
        "announcements": len(announcements),
        "discussions": len(discussions),
        "posts": posts,
        "gradebook_columns": len(columns),
        "attempts": len(attempts),
        "external_links": len(dedupe_external(external)),
        "external_videos": sorted({e["url"] for e in external if e["video"]}),
        "errors": len(errors),
        "gone": len(gone),
    }
    dump("summary.json", summary)
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
        p.add_argument("--credential", help="a kind=dir credential, where the run was handed none")
        p.add_argument("--headed", action="store_true")
        p.add_argument("--site", help="the site's base url, over the credential's host (a job's target names it)")
        p.add_argument("--sso", help="the SAML provider (`apId`, e.g. _4405_1) to renew an expired session through, where the sign-in page offers several")
        return p

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

    host_site = resolve_credential(args)
    site = as_site(args.site) if args.site else host_site
    if not site:
        print("no site: pass --site https://<your-blackboard-host>, or name a credential whose host is the site", file=sys.stderr)
        return EXIT_USAGE

    # Here, not at the top: every helper above runs, and is tested, without a browser.
    import llm_wiki_browser
    from playwright.sync_api import sync_playwright

    command = {"whoami": cmd_whoami, "courses": cmd_courses, "get": cmd_get, "harvest": cmd_harvest}[args.cmd]
    try:
        with sync_playwright() as pw, llm_wiki_browser.open_context(pw, headless=not args.headed, context={"accept_downloads": True}) as ctx:
            return command(Session(ctx, site, sso=args.sso), args)
    except AuthError as e:
        print(f"auth: {e} — a person runs `llm-wiki-ops credentials login <credential>` again", file=sys.stderr)
        return EXIT_AUTH
    except ApiError as e:
        print(f"api: {e}", file=sys.stderr)
        return EXIT_API
    except llm_wiki_browser.SaveFailed as e:
        print(f"credential_store_error: {e}", file=sys.stderr)
        return EXIT_STORE


if __name__ == "__main__":
    sys.exit(main())
