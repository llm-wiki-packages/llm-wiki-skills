#!/usr/bin/env python3
"""channel-github process — the pen for one repo's page.

Two subcommands, run by the process session through `llm-wiki-ops run` (which
starts them at the wiki root, so every path is wiki-relative and verbatim off
the ticket):

    page.py prepare <capture_dir> --ticket <id>
        What the session needs to judge the repo: its facts, where its README
        is, and the page the wiki ALREADY holds for it — by title, else by
        `resource` anywhere under `dest` (a Web Clipper clip lands there under
        whatever name the clipper gave it). Prints JSON.

    page.py write <capture_dir> --ticket <id> --from <judgment.json> [--readme full|excerpt|none]
        Renders the page from the capture plus the session's judgment, writes
        it through `page create` (or `page edit` over the page already held),
        merges with that page — its tags and its `## Notes` section survive —
        and posts `tickets update` with `written_from`.

The judgment file is the session's whole say:

    {"keep": true, "junk": null,
     "description": "<one sentence, <=200 chars, no wikilinks>",
     "summary": "<2-4 information-dense sentences>",
     "use_for": ["<a concrete job this repo does>", ...],
     "categories": ["<a category from the wiki's channel-github policy>", ...]}

Everything else on the page — the facts line, the frontmatter, the README — is
this script's, from the capture, so a page always says what GitHub said.

stdlib only: the process slice has no network.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from door import open_ticket, ops_json, post_update

CAPTURE_NAME = "capture.json"
REPO_NAME = "repo.json"
README_NAME = "README.md"
WRITTEN_NAME = "written.json"
JUDGMENT_FIELDS = ("keep", "junk", "description", "summary", "use_for", "categories")
SIGNAL_TAGS = ("github", "gh-starred", "gh-clipped", "gh-watched")
DESCRIPTION_MAX = 200
CATEGORIES_MAX = 6
EXCERPT_LINES = 150
EXCERPT_CHARS = 12_000
FULL_CHARS = 60_000
NOTES_HEADING = "## Notes"
README_HEADING = "## README"


def die(msg, code=2):
    print(f"page: {msg}", file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ the held page


def norm_url(url: str) -> str:
    url = (url or "").strip().strip("\"'").rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    return re.sub(r"^http://", "https://", url).replace("://www.github.com/", "://github.com/").lower()


RESOURCE_LINE = re.compile(r"^resource:\s*(.+?)\s*$", re.M)


def frontmatter_text(text: str) -> tuple[str, str]:
    """`(frontmatter block, body)`; an absent block is `("", text)`."""
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 4)
            return text[4:end], (text[nl + 1 :] if nl != -1 else "")
    return "", text


def find_held(dest: Path, title: str, url: str) -> Path | None:
    """The page `dest` already holds for this repo: `<title>.md`, else the
    first page whose `resource` is this repo's URL (a clip under the
    clipper's own name). `_versions/` is history, never a candidate."""
    direct = dest / f"{title}.md"
    if direct.is_file():
        return direct
    want = norm_url(url)
    if not dest.is_dir():
        return None
    for path in sorted(dest.rglob("*.md")):
        if "_versions" in path.parts:
            continue
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        fm, _ = frontmatter_text(head)
        m = RESOURCE_LINE.search(fm)
        if m and norm_url(m.group(1)) == want:
            return path
    return None


def held_frontmatter(path: Path) -> dict:
    rc, answer = ops_json("page", "read", path.as_posix(), "--frontmatter")
    fm = answer.get("frontmatter") if rc == 0 else None
    return fm if isinstance(fm, dict) else {}


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in value.strip("[]").split(",") if v.strip()]
    return []


def section(body: str, heading: str) -> str | None:
    """The text under `heading` (an exact `## ` line) up to the next `## `
    heading, outside code fences; None when the page has no such heading."""
    lines = body.splitlines()
    out, inside, fence = [], False, False
    for line in lines:
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if not fence and line.startswith("## "):
            if inside:
                break
            if line.strip() == heading:
                inside = True
                continue
        if inside:
            out.append(line)
    return "\n".join(out).strip("\n") if inside else None


# ------------------------------------------------------------------ rendering


def fmt_count(n: int) -> str:
    return f"{n:,}"


def one_line(text, cap=None) -> str:
    text = " ".join(str(text or "").split())
    text = text.replace("[[", "").replace("]]", "")
    if cap and len(text) > cap:
        text = text[: cap - 1].rstrip() + "…"
    return text


def kebab(text) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def demote(markdown: str, by: int = 2) -> str:
    """README headings nest under `## README`: `#` → `###`, capped at six,
    never inside a code fence."""
    out, fence = [], False
    for line in markdown.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})(\s.*)$", line)
        out.append(("#" * min(6, len(m.group(1)) + by)) + m.group(2) if m else line)
    return "\n".join(out)


def readme_part(readme: str | None, mode: str) -> str:
    if mode == "none" or not readme:
        return ""
    text = readme.strip()
    if mode == "excerpt":
        lines = text.splitlines()[:EXCERPT_LINES]
        text = "\n".join(lines)[:EXCERPT_CHARS]
        cut = text != readme.strip()
    else:
        cut = len(text) > FULL_CHARS
        text = text[:FULL_CHARS]
    if text.count("```") % 2:
        text += "\n```"
    body = demote(text)
    if cut:
        body += "\n\n*(README truncated — the full text is at the repo.)*"
    return body


def facts_line(repo: dict) -> str:
    bits = [f"**[{repo['full_name']}]({repo['url']})**", f"★ {fmt_count(repo['stars'])} as of {repo['seen']}"]
    prev = repo.get("prev") or {}
    if prev.get("stars") is not None and prev.get("at"):
        gain = repo["stars"] - int(prev["stars"])
        if gain:
            bits.append(f"{'+' if gain > 0 else ''}{fmt_count(gain)} since {prev['at']}")
    for key in ("language", "license"):
        if repo.get(key):
            bits.append(repo[key])
    if repo.get("created"):
        bits.append(f"created {repo['created']}")
    if repo.get("pushed"):
        bits.append(f"last push {repo['pushed']}")
    return " · ".join(bits)


def provenance(repo: dict, clipped: bool) -> str:
    bits = []
    if repo.get("starred_at"):
        bits.append(f"starred {repo['starred_at']}")
    if clipped:
        bits.append("clipped")
    bits.extend(f"`{v}`" for v in repo.get("via") or [])
    return " · ".join(bits)


def render_body(repo: dict, judgment: dict, readme: str | None, notes: str | None, clipped: bool, mode: str) -> str:
    parts = []
    summary = one_line(judgment.get("summary")) or one_line(repo.get("description")) or "No description."
    parts.append(f"> [!summary]\n> {summary}")
    head = [facts_line(repo)]
    if repo.get("archived"):
        head.append("**Archived** — read-only on GitHub.")
    parts.append("\n".join(head))
    meta = []
    if repo.get("topics"):
        meta.append(f"- Topics: {', '.join(repo['topics'])}")
    if repo.get("homepage"):
        meta.append(f"- Homepage: {repo['homepage']}")
    prov = provenance(repo, clipped)
    if prov:
        meta.append(f"- How it got here: {prov}")
    if meta:
        parts.append("\n".join(meta))
    uses = [one_line(u, 240) for u in judgment.get("use_for") or [] if one_line(u)]
    if uses:
        parts.append("## What it's for\n\n" + "\n".join(f"- {u}" for u in uses))
    parts.append(f"{NOTES_HEADING}\n\n{notes.strip()}" if notes and notes.strip() else NOTES_HEADING)
    readme_md = readme_part(readme, mode)
    if readme_md:
        parts.append(f"{README_HEADING}\n\n{readme_md}")
    return "\n\n".join(parts).rstrip() + "\n"


def page_keys(repo: dict, judgment: dict, held_fm: dict, clipped: bool) -> dict:
    """Frontmatter this unit owns. A value it does not know is left out,
    never written empty, so a page edit keeps what the clipper set."""
    cats = []
    for c in judgment.get("categories") or []:
        k = kebab(c)
        if k and k not in cats and k not in SIGNAL_TAGS:
            cats.append(k)
    signals = ["github"]
    if repo.get("starred_at") or held_fm.get("gh_starred_at"):
        signals.append("gh-starred")
    if clipped:
        signals.append("gh-clipped")
    if any(not v.startswith("stars:") for v in repo.get("via") or []):
        signals.append("gh-watched")
    tags = []
    for t in [*as_list(held_fm.get("tags")), *signals, *cats[:CATEGORIES_MAX]]:
        t = kebab(t)
        if t and t not in tags and t != "clip":
            tags.append(t)
    description = one_line(judgment.get("description") or repo.get("description"), DESCRIPTION_MAX)
    prev = repo.get("prev") or {}
    keys = {
        "type": "repo",
        "resource": repo["url"],
        "description": description,
        "author": repo.get("owner"),
        "source_host": "github.com",
        "published": repo.get("created"),
        "tags": ",".join(tags),
        "extracted": "true",
        "gh_stars": repo["stars"],
        "gh_seen": repo["seen"],
        "gh_stars_prev": prev.get("stars"),
        "gh_stars_prev_at": prev.get("at"),
        "gh_forks": repo.get("forks"),
        "gh_language": repo.get("language"),
        "gh_topics": ", ".join(repo.get("topics") or []),
        "gh_license": repo.get("license"),
        "gh_archived": "true" if repo.get("archived") else None,
        "gh_pushed": repo.get("pushed"),
        "gh_starred_at": repo.get("starred_at"),
        "gh_via": ", ".join(repo.get("via") or []),
        "gh_first_seen": held_fm.get("gh_first_seen") or repo["seen"],
    }
    return {k: v for k, v in keys.items() if v not in (None, "")}


# ------------------------------------------------------------------ io


def load_capture(capture_dir: Path) -> tuple[dict, dict, str | None]:
    try:
        capture = json.loads((capture_dir / CAPTURE_NAME).read_text(encoding="utf-8"))
        repo = json.loads((capture_dir / REPO_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"no repo capture in {capture_dir} ({e}) — harvest leaves {CAPTURE_NAME} and {REPO_NAME}")
    readme_path = capture_dir / README_NAME
    readme = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path.is_file() else None
    return capture, repo, readme


def load_judgment(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"judgment {path}: {e}")
    if not isinstance(data, dict):
        die(f"judgment {path}: not an object")
    extra = set(data) - set(JUDGMENT_FIELDS)
    if extra:
        die(f"judgment {path}: unknown keys {sorted(extra)} (allowed: {', '.join(JUDGMENT_FIELDS)})")
    return data


def write_page(dest: str, title: str, held: Path | None, keys: dict, body: str) -> str:
    pairs = [f"{k}={v}" for k, v in keys.items()]
    if held is None:
        rc, answer = ops_json("page", "create", f"title={title}", f"dest={dest}", *pairs, "--stdin", stdin=body)
        if rc == 2 and "already exists" in str(answer.get("error") or ""):
            held = Path(dest) / f"{title}.md"
        elif rc != 0 or not answer.get("path"):
            die(f"`page create` refused ({rc}): {answer.get('error') or answer}")
        else:
            return answer["path"]
    rc, answer = ops_json("page", "edit", held.as_posix(), *pairs, "--stdin", stdin=body)
    if rc != 0:
        die(f"`page edit {held}` refused ({rc}): {answer.get('error') or answer}")
    return answer.get("path") or held.as_posix()


# ------------------------------------------------------------------ commands


def cmd_prepare(a) -> int:
    capture_dir = Path(a.capture_dir)
    ticket = open_ticket(a.ticket, "process")
    dest = ticket.get("dest") or die("the ticket names no dest")
    capture, repo, readme = load_capture(capture_dir)
    title = capture.get("title") or repo["full_name"].replace("/", "--")
    held = find_held(Path(dest), title, repo["url"])
    held_fm = held_frontmatter(held) if held else {}
    held_tags = as_list(held_fm.get("tags"))
    print(
        json.dumps(
            {
                "repo": repo["full_name"],
                "url": repo["url"],
                "change": repo.get("change"),
                "title": title,
                "dest": dest,
                "description": repo.get("description"),
                "topics": repo.get("topics"),
                "language": repo.get("language"),
                "stars": repo.get("stars"),
                "archived": repo.get("archived"),
                "readme": (capture_dir / README_NAME).as_posix() if readme is not None else None,
                "readme_chars": len(readme or ""),
                "held": {
                    "path": held.as_posix(),
                    "clipped": "gh-clipped" in held_tags or held_fm.get("type") == "clip" or not held_fm.get("harvested"),
                    "categories": [t for t in held_tags if t not in SIGNAL_TAGS and t != "clip"],
                }
                if held
                else None,
                "judgment": {k: None for k in JUDGMENT_FIELDS},
                "next": f"write {capture_dir.as_posix()}/judgment.json, then: page.py write {capture_dir.as_posix()} --ticket {a.ticket} --from judgment.json",
            },
            indent=1,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_write(a) -> int:
    capture_dir = Path(a.capture_dir)
    ticket = open_ticket(a.ticket, "process")
    dest = ticket.get("dest") or die("the ticket names no dest")
    capture, repo, readme = load_capture(capture_dir)
    source = Path(a.from_)
    # A bare name is the session's own file beside the capture: the one
    # directory its slice writes besides `dest`.
    judgment = load_judgment(capture_dir / source if len(source.parts) == 1 else source)
    title = capture.get("title") or repo["full_name"].replace("/", "--")
    held = find_held(Path(dest), title, repo["url"])
    held_fm = held_frontmatter(held) if held else {}
    clipped = bool(held) and ("gh-clipped" in as_list(held_fm.get("tags")) or held_fm.get("type") == "clip" or not held_fm.get("harvested"))

    if judgment.get("keep") is False and not held:
        why = one_line(judgment.get("junk") or "junk", 120)
        return 0 if post_update(a.ticket, "process", "ok", reason=f"{repo['full_name']}: no page — {why}") == 0 else 2

    notes = None
    if held:
        try:
            _, held_body = frontmatter_text(held.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            held_body = ""
        notes = section(held_body, NOTES_HEADING)
    body = render_body(repo, judgment, readme, notes, clipped, a.readme)
    keys = page_keys(repo, judgment, held_fm, clipped)
    path = write_page(dest, title, held, keys, body)

    (capture_dir / WRITTEN_NAME).write_text(json.dumps([path]) + "\n", encoding="utf-8")
    reason = f"{repo['full_name']} ({repo.get('change')}) → {path}" + (" — merged with the clip" if clipped else "")
    rc = post_update(a.ticket, "process", "ok", reason=reason, written_from=WRITTEN_NAME)
    print(json.dumps({"written": [path], "merged_clip": clipped, "reason": reason}, indent=1))
    return 0 if rc == 0 else 2


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="page.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("prepare")
    pr.add_argument("capture_dir")
    pr.add_argument("--ticket", required=True)
    w = sub.add_parser("write")
    w.add_argument("capture_dir")
    w.add_argument("--ticket", required=True)
    w.add_argument("--from", dest="from_", required=True, help="the judgment file; a bare name is read from the capture directory")
    w.add_argument("--readme", choices=("full", "excerpt", "none"), default="full")
    a = p.parse_args(argv)
    return cmd_prepare(a) if a.cmd == "prepare" else cmd_write(a)


if __name__ == "__main__":
    sys.exit(main())
