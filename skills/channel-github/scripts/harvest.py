#!/usr/bin/env python3
"""channel-github harvest — the whole worker for the `harvest` stage.

A script stage: the runner starts it with no session, in the stage's jail, as

    llm-wiki-ops run ops/skills/channel-github/scripts/harvest.py ticket=<id>

It reads the ticket (`options.select`, `capture_dir`, `known[]`, `credential_mode`),
enumerates every repo the job's selectors name through the GitHub REST API
(metadata only — one call per 100 repos), decides which repos earn a capture,
and fills one leaf directory per captured repo:

    _raw/<slug>/<owner-repo>--<hash8>[-<YYYYMMDD>]/
        repo.json      the normalized repo facts, the selectors that named it,
                       why it was captured (`change`) and what this job saw
                       last time (`prev`)
        README.md      the README as GitHub serves it raw, when there is one
        capture.json   the flat index `close` reads

A repo earns a capture when it is NEW to the job (not in `known[]`, never
captured here) or, already held, when it CHANGED enough to rewrite its page:
stars jumped (`jump_abs` / `jump_pct`), a push landed after a capture older
than `refresh_days`, or a selector newly names it (newly starred). Everything
else is counted and skipped. The job's own state — the last stars seen per
repo, a short stars history, what was captured when — is
`_raw/<slug>/.state.json`, written only AFTER `tickets update` was accepted, so
a refused update leaves the state where it was.

stdlib only: a script stage refuses a PEP 723 block.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from door import open_ticket, post_update

API = "https://api.github.com"
API_HOST = "api.github.com"
# The `github` route's phantom: on `credential_mode: route` the jail holds it
# here and the proxy puts the real token on requests bound for the API host.
ROUTE_ENV = "GITHUB_TOKEN"
UA = {"User-Agent": "llm-wiki-channel-github", "X-GitHub-Api-Version": "2022-11-28"}

CAPTURE_NAME = "capture.json"
REPO_NAME = "repo.json"
README_NAME = "README.md"
STATE_NAME = ".state.json"
STATE_V = 1
HISTORY_MAX = 12  # stars observations kept per repo, one per day at most

# What a job's `options` may override; every one has a `watch.inputs` default.
DEFAULTS = {
    "max_captures": 150,  # leaves per run; the rest waits for the next run (`partial`)
    "jump_abs": 500,  # stars gained since the last capture that rewrite a page...
    "jump_pct": 25,  # ...or this percent, when the gain is also >= JUMP_FLOOR
    "refresh_days": 90,  # a push after a capture this old re-captures
    "include_forks": False,
    "include_archived": True,
    "search_limit": 100,
}
JUMP_FLOOR = 50
DEADLINE_S = 20 * 60
BACKOFF_TRIES = 4
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
KINDS = ("stars", "org", "user", "repo", "search")
_NON_SLUG = re.compile(r"[^a-z0-9]+")


class ApiError(Exception):
    """A refusal that ends enumeration: `why` is one of denied|timeout|auth|error."""

    def __init__(self, url, why, said):
        super().__init__(f"{url}: {why} — {said}")
        self.url, self.why, self.said = url, why, said


class NotFound(Exception):
    pass


# ------------------------------------------------------------------ selectors


def parse_selectors(raw) -> list[tuple[str, str]]:
    """`options.select` → `[(kind, value)]`. Comma- or newline-separated;
    `stars:<user>`, `org:<org>`, `user:<user>`, `repo:<owner>/<name>`,
    `search:<query>`. A bad entry is refused loudly, never skipped."""
    if isinstance(raw, list):
        parts = [str(p) for p in raw]
    else:
        parts = re.split(r"[,\n]", str(raw or ""))
    out = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        kind, sep, value = part.partition(":")
        kind, value = kind.strip().lower(), value.strip()
        if not sep or kind not in KINDS or not value:
            raise ValueError(f"selector {part!r}: expected one of {', '.join(k + ':<…>' for k in KINDS)}")
        if kind == "repo":
            owner, slash, name = value.partition("/")
            if not slash or not NAME_RE.match(owner) or not NAME_RE.match(name):
                raise ValueError(f"selector {part!r}: repo:<owner>/<name>")
        elif kind != "search" and not NAME_RE.match(value):
            raise ValueError(f"selector {part!r}: not a GitHub login")
        out.append((kind, value))
    if not out:
        raise ValueError("options.select names no selector — `llm-wiki-ops jobs edit <slug> options.select=stars:<login>`")
    return out


def selector_label(kind, value) -> str:
    return f"{kind}:{value}"


# ------------------------------------------------------------------ the repo


def day(value) -> str | None:
    """An ISO timestamp's `YYYY-MM-DD`, or None."""
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    return None


def page_title(full_name: str) -> str:
    """`owner--repo`: the page's title and filename. `/` cannot be in a
    filename and `--` cannot be in a GitHub login, so the split is exact."""
    owner, _, name = full_name.partition("/")
    return f"{owner}--{name}"


def normalize(raw: dict, *, via: str, starred_at: str | None = None) -> dict:
    """GitHub's repo object → the facts this unit keeps. Venue text stays as
    served; the process step decides what reaches the page."""
    lic = raw.get("license") if isinstance(raw.get("license"), dict) else {}
    owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
    return {
        "full_name": raw.get("full_name") or "",
        "owner": owner.get("login") or (raw.get("full_name") or "").split("/")[0],
        "name": raw.get("name") or "",
        "url": raw.get("html_url") or f"https://github.com/{raw.get('full_name')}",
        "description": raw.get("description") or "",
        "homepage": raw.get("homepage") or "",
        "stars": int(raw.get("stargazers_count") or 0),
        "forks": int(raw.get("forks_count") or 0),
        "language": raw.get("language") or "",
        "topics": [t for t in (raw.get("topics") or []) if isinstance(t, str)],
        "license": (lic or {}).get("spdx_id") or "",
        "archived": bool(raw.get("archived")),
        "fork": bool(raw.get("fork")),
        "created": day(raw.get("created_at")),
        "pushed": day(raw.get("pushed_at")),
        "default_branch": raw.get("default_branch") or "",
        "starred_at": day(starred_at),
        "via": [via],
    }


def merge_repo(seen: dict, repo: dict) -> None:
    """Fold one sighting into `seen` (keyed by lowercased full name): the
    union of selectors, the earliest starred date."""
    key = repo["full_name"].lower()
    have = seen.get(key)
    if have is None:
        seen[key] = repo
        return
    for v in repo["via"]:
        if v not in have["via"]:
            have["via"].append(v)
    if repo.get("starred_at") and not have.get("starred_at"):
        have["starred_at"] = repo["starred_at"]


def keep(repo: dict, opts: dict, kind: str) -> bool:
    """Forks and archived repos, by the job's options. A repo named outright
    (`repo:`) or starred by hand is always kept."""
    if kind in ("repo", "stars"):
        return True
    if repo["fork"] and not opts["include_forks"]:
        return False
    if repo["archived"] and not opts["include_archived"]:
        return False
    return True


# ------------------------------------------------------------------ change


def days_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    ta = time.mktime(time.strptime(a, "%Y-%m-%d"))
    tb = time.mktime(time.strptime(b, "%Y-%m-%d"))
    return int(round((tb - ta) / 86400))


def decide(repo: dict, prev: dict | None, held: bool, opts: dict, today: str) -> str | None:
    """Why this repo earns a capture now, or None.

    `new` — the job holds no page and never captured it. Otherwise, against
    what the last CAPTURE saw (not the last sighting, so a slow climb still
    adds up): `jump` — stars rose by `jump_abs`, or by `jump_pct` percent and
    at least JUMP_FLOOR; `starred` — a stars selector names a repo the job
    held without one (clipped first, starred later); `via` — another
    selector of this job names it now; `stale` — pushed after a capture older
    than `refresh_days`."""
    if not held and not (prev and prev.get("captured_at")):
        return "new"
    if not prev or not prev.get("captured_at"):
        return None  # held by a page, never captured here: baseline only
    base = int(prev.get("stars_at_capture") or 0)
    gain = repo["stars"] - base
    if gain >= opts["jump_abs"]:
        return "jump"
    if base > 0 and gain >= JUMP_FLOOR and gain * 100 >= opts["jump_pct"] * base:
        return "jump"
    if repo.get("starred_at") and not prev.get("starred_at"):
        return "starred"
    if any(v not in (prev.get("via") or []) for v in repo["via"]):
        return "via"
    age = days_between(prev.get("captured_at"), today)
    if repo.get("pushed") and age is not None and age >= opts["refresh_days"]:
        if repo["pushed"] > prev["captured_at"]:
            return "stale"
    return None


def order_key(repo: dict, change: str):
    """New first, then the biggest movers; within a kind, newest star and
    most stars first — a capped run spends its budget on what matters."""
    rank = {"new": 0, "starred": 1, "jump": 2, "via": 3, "stale": 4}[change]
    return (rank, -(int((repo.get("starred_at") or "0000-00-00").replace("-", ""))), -repo["stars"])


def leaf_name(url: str, dated: str | None = None) -> str:
    """`<owner-repo>--<hash8>` — the host's shape for an addressed item. An
    update capture is dated (`-<YYYYMMDD>`) so it is a directory the queue has
    never seen, and mints a process ticket of its own."""
    parts = urllib.parse.urlsplit(url)
    bits = [b for b in parts.path.split("/") if b] or [parts.netloc.lower()]
    folded = _NON_SLUG.sub("-", "-".join(bits).lower()).strip("-")[:60] or "item"
    name = f"{folded}--{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}"
    return f"{name}-{dated.replace('-', '')}" if dated else name


def record_history(entry: dict, stars: int, today: str) -> list:
    hist = [h for h in (entry.get("history") or []) if isinstance(h, list) and len(h) == 2]
    if hist and hist[-1][0] == today:
        hist[-1] = [today, stars]
    else:
        hist.append([today, stars])
    return hist[-HISTORY_MAX:]


# ------------------------------------------------------------------ network


def _get(url, token, accept="application/vnd.github+json"):
    """One GET. Returns `(body bytes, headers)`. 404/410 raise NotFound; a
    401, a bad credential or an exhausted rate limit raise ApiError(auth); a
    proxy refusal ApiError(denied); a timeout ApiError(timeout)."""
    headers = {**UA, "Accept": accept}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last = None
    for attempt in range(BACKOFF_TRIES):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            said = e.read()[:300].decode("utf-8", "replace")
            if e.code in (404, 410):
                raise NotFound(url) from None
            if e.code == 401:
                raise ApiError(url, "auth", f"401 {said}") from None
            remaining = e.headers.get("X-RateLimit-Remaining")
            if e.code in (403, 429) and remaining == "0":
                raise ApiError(url, "auth", f"rate limit exhausted (resets {e.headers.get('X-RateLimit-Reset')}); a token raises it") from None
            if e.code in (403, 429) and "rate limit" in said.lower():
                last = ApiError(url, "error", f"{e.code} secondary rate limit")
                time.sleep(min(int(e.headers.get("Retry-After") or 60), 300))
                continue
            if e.code == 403 and not e.headers.get("X-GitHub-Request-Id"):
                raise ApiError(url, "denied", f"403 not from GitHub (a proxy refusal): {said[:120]}") from None
            if e.code >= 500:
                last = ApiError(url, "error", f"{e.code}")
                time.sleep(2 ** attempt)
                continue
            raise ApiError(url, "error", f"{e.code} {said}") from None
        except (TimeoutError, socket.timeout) as e:
            last = ApiError(url, "timeout", str(e))
            time.sleep(2 ** attempt)
        except urllib.error.URLError as e:
            reason = str(e.reason)
            if isinstance(e.reason, (TimeoutError, socket.timeout)) or "timed out" in reason:
                last = ApiError(url, "timeout", reason)
                time.sleep(2 ** attempt)
                continue
            raise ApiError(url, "denied", reason) from None
    raise last or ApiError(url, "error", "no answer")


def _next_link(headers) -> str | None:
    for part in (headers.get("Link") or "").split(","):
        m = re.match(r'\s*<([^>]+)>;\s*rel="next"', part)
        if m:
            return m.group(1)
    return None


def paged(url, token, accept="application/vnd.github+json", limit=None, key=None):
    """Every item behind a paginated listing, following `Link: rel=next`."""
    got = []
    while url:
        body, headers = _get(url, token, accept)
        data = json.loads(body)
        items = data.get(key, []) if key else data
        got.extend(items)
        if limit and len(got) >= limit:
            return got[:limit]
        url = _next_link(headers)
    return got


def enumerate_selector(kind, value, token, opts) -> list[dict]:
    label = selector_label(kind, value)
    q = urllib.parse.quote
    if kind == "stars":
        rows = paged(f"{API}/users/{q(value)}/starred?per_page=100", token, accept="application/vnd.github.star+json")
        return [normalize(r["repo"], via=label, starred_at=r.get("starred_at")) for r in rows if isinstance(r, dict) and "repo" in r]
    if kind == "org":
        rows = paged(f"{API}/orgs/{q(value)}/repos?per_page=100&type=public&sort=pushed", token)
    elif kind == "user":
        rows = paged(f"{API}/users/{q(value)}/repos?per_page=100&type=owner&sort=pushed", token)
    elif kind == "repo":
        body, _ = _get(f"{API}/repos/{value}", token)
        rows = [json.loads(body)]
    else:  # search
        qs = urllib.parse.urlencode({"q": value, "sort": "stars", "order": "desc", "per_page": 100})
        rows = paged(f"{API}/search/repositories?{qs}", token, limit=opts["search_limit"], key="items")
    return [r for r in (normalize(x, via=label) for x in rows if isinstance(x, dict)) if keep(r, opts, kind)]


def fetch_readme(full_name, token) -> str | None:
    try:
        body, _ = _get(f"{API}/repos/{full_name}/readme", token, accept="application/vnd.github.raw")
    except NotFound:
        return None
    return body.decode("utf-8", "replace")


# ------------------------------------------------------------------ credential


def get_token(ticket: dict) -> str | None:
    """The route's phantom on `credential_mode: route`, else None — keyless:
    60 requests an hour, enough for a few dozen repos per run. The mode word
    is the signal, never the variable's presence: a route nothing fills is
    omitted from the jail."""
    mode = ticket.get("credential_mode") or os.environ.get("LLM_WIKI_CREDENTIAL_MODE") or "none"
    if mode != "route":
        return None
    phantom = os.environ.get(ROUTE_ENV)
    if not phantom:
        raise ApiError(API, "auth", f"credential_mode is route but the jail holds no {ROUTE_ENV}: the unit's sandbox.jsonc lacks the `github` route on its harvest stage")
    return phantom


# ------------------------------------------------------------------ io


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def job_options(ticket: dict) -> dict:
    raw = ticket.get("options") if isinstance(ticket.get("options"), dict) else {}
    opts = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in raw or raw[key] in (None, ""):
            continue
        val = raw[key]
        if isinstance(default, bool):
            opts[key] = str(val).strip().lower() in ("1", "true", "yes", "on")
        else:
            try:
                opts[key] = int(val)
            except (TypeError, ValueError):
                sys.exit(f"harvest: options.{key}={val!r} is not a number")
    return opts


def write_leaf(raw_root: Path, slug: str, repo: dict, readme: str | None, change: str, prev: dict | None, today: str) -> str:
    leaf = leaf_name(repo["url"], None if change == "new" else today)
    d = raw_root / leaf
    d.mkdir(parents=True, exist_ok=True)
    facts = {**repo, "change": change, "seen": today}
    facts["prev"] = {"stars": prev.get("stars_at_capture"), "at": prev.get("captured_at")} if prev and prev.get("captured_at") else None
    _dump(d / REPO_NAME, facts)
    if readme is not None:
        (d / README_NAME).write_text(readme, encoding="utf-8")
    _dump(
        d / CAPTURE_NAME,
        {
            "v": 1,
            "slug": slug,
            "item": repo["url"],
            "title": page_title(repo["full_name"]),
            "body": README_NAME if readme is not None else REPO_NAME,
            "content_type": "text/markdown" if readme is not None else "application/json",
            "fetched_at": now_iso(),
            "change": change,
        },
    )
    return f"{raw_root.as_posix()}/{leaf}"


# ------------------------------------------------------------------ main


def run(ticket_id: str) -> int:
    started = time.monotonic()
    ticket = open_ticket(ticket_id, "harvest")
    slug = ticket.get("slug") or ""
    capture_dir = Path(ticket.get("capture_dir") or "")
    if not slug or not ticket.get("capture_dir"):
        sys.exit("harvest: the ticket names no slug or capture_dir")
    raw_root = capture_dir.parent  # `_raw/<slug>`, wiki-relative: `run` starts at the wiki root
    capture_dir.mkdir(parents=True, exist_ok=True)
    try:
        selectors = parse_selectors((ticket.get("options") or {}).get("select"))
    except ValueError as e:
        post_update(ticket_id, "harvest", "failed", reason=str(e))
        return 1
    opts = job_options(ticket)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    known = {str(k.get("resource", "")).rstrip("/").lower() for k in (ticket.get("known") or []) if isinstance(k, dict)}
    state = _load(raw_root / STATE_NAME, {})
    if state.get("v") != STATE_V:
        state = {"v": STATE_V, "repos": {}}
    repos_state = state["repos"]

    missing, notes = [], []
    try:
        token = get_token(ticket)
    except ApiError as e:
        post_update(ticket_id, "harvest", "failed", reason=e.said, missing=[(API_HOST, e.url, e.why)])
        return 1
    if not token:
        notes.append("keyless (60 requests/hour): store a token for more")

    seen: dict[str, dict] = {}
    for kind, value in selectors:
        try:
            for repo in enumerate_selector(kind, value, token, opts):
                merge_repo(seen, repo)
        except NotFound:
            notes.append(f"{selector_label(kind, value)}: not found")
        except ApiError as e:
            missing.append((API_HOST, e.url, e.why))
            notes.append(f"{selector_label(kind, value)}: {e.why} ({e.said[:120]})")

    plan = []
    for key, repo in seen.items():
        prev = repos_state.get(key)
        change = decide(repo, prev, repo["url"].rstrip("/").lower() in known, opts, today)
        if change:
            plan.append((repo, change, prev))
    plan.sort(key=lambda p: order_key(p[0], p[1]))
    capped = len(plan) > opts["max_captures"]
    plan = plan[: opts["max_captures"]]

    captured, done_keys, stopped = [], set(), None
    for repo, change, prev in plan:
        if time.monotonic() - started > DEADLINE_S:
            stopped = "deadline"
            break
        try:
            readme = fetch_readme(repo["full_name"], token)
        except ApiError as e:
            missing.append((API_HOST, e.url, e.why))
            if e.why in ("auth", "denied"):
                stopped = f"{e.why} on README fetch"
                break
            continue
        captured.append(write_leaf(raw_root, slug, repo, readme, change, prev, today))
        done_keys.add(repo["full_name"].lower())

    counts = {c: sum(1 for _, ch, _ in plan if ch == c) for c in ("new", "starred", "jump", "via", "stale")}
    reason = (
        f"{len(seen)} repos from {len(selectors)} selector(s); captured {len(captured)} "
        f"({', '.join(f'{k} {v}' for k, v in counts.items() if v) or 'nothing changed'})"
    )
    if capped:
        reason += f"; capped at max_captures={opts['max_captures']}, the rest next run"
    if stopped:
        reason += f"; stopped: {stopped}"
    if notes:
        reason += "; " + "; ".join(notes)

    if not seen and missing:
        status = "failed"
    elif capped or stopped or (missing and captured):
        status = "partial"
    else:
        status = "ok"
    if post_update(ticket_id, "harvest", status, reason=reason, captured=captured, missing=missing) != 0:
        return 2  # the state stays where it was: nothing here was accepted

    for key, repo in seen.items():
        entry = dict(repos_state.get(key) or {})
        entry.update(
            {
                "stars": repo["stars"],
                "seen": today,
                "pushed": repo.get("pushed"),
                "starred_at": repo.get("starred_at") or entry.get("starred_at"),
                "via": sorted(set(entry.get("via") or []) | set(repo["via"])),
                "history": record_history(entry, repo["stars"], today),
            }
        )
        if key in done_keys:
            entry["captured_at"] = today
            entry["stars_at_capture"] = repo["stars"]
        repos_state[key] = entry
    state["updated"] = now_iso()
    _dump(raw_root / STATE_NAME, state)
    print(json.dumps({"status": status, "reason": reason, "captured": len(captured)}, indent=1))
    return 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # The runner passes `ticket=<id>`; `--ticket <id>` is accepted for a hand test.
    ticket = None
    for i, a in enumerate(args):
        if a.startswith("ticket="):
            ticket = a.split("=", 1)[1]
        elif a == "--ticket" and i + 1 < len(args):
            ticket = args[i + 1]
    if not ticket:
        argparse.ArgumentParser(prog="harvest.py", usage="harvest.py ticket=<id>").error("ticket=<id> is required")
    return run(ticket)


if __name__ == "__main__":
    sys.exit(main())
