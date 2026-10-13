#!/usr/bin/env python3
"""channel-github's catalog: what the wiki's GitHub repo pages say, ranked
and listed.

Everything here is computed from the frontmatter `page.py` writes (and the
GitHub clip template mirrors) on the repo pages. No state of its own, no
network, no writes: the routine's `lists.py` writes the list pages, and a
session edits a repo page through `page edit`. Run at the wiki root through
the front door:

    llm-wiki-ops run ops/skills/channel-github/scripts/catalog.py <cmd> ...

    census                     tags, areas and types across wiki/ and sources/,
                               plus the repo categories in use — setup's input
    scan                       every repo page as JSON (path, facts, tags, signals)
    rank                       a ranked table of repo pages, filtered by tags,
                               words, or a candidate list from `search query`
    preview [--only N]         the list pages `references/lists.json` declares,
                               printed, never written
    pending                    clipped repos with no GitHub facts yet, as the
                               `repo:` selectors that would fill them in

stdlib only.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LISTS_JSON = HERE.parent / "references" / "lists.json"
SIGNAL_TAGS = ("github", "gh-starred", "gh-clipped", "gh-watched", "github-list", "clip")
REPO_URL = re.compile(r"^https?://(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9-]*)/([A-Za-z0-9._-]+?)(?:\.git)?/?$", re.I)
DEFAULT_WEIGHTS = {
    "stars": 1.0,  # x log10(stars + 1): 1k ≈ 3, 100k ≈ 5
    "starred": 2.0,
    "clipped": 1.5,
    "watched": 0.5,
    "recent": 0.5,  # pushed within recent_days
    "recent_days": 180,
    "archived": -2.0,
    "jump": 1.0,  # x log10(gain + 1), for gains since the previous capture
}


def die(msg, code=2):
    print(f"catalog: {msg}", file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ frontmatter


def _scalar(raw: str):
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        q = v[0]
        v = v[1:-1]
        return v.replace("''", "'") if q == "'" else v.replace('\\"', '"')
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if v in ("null", "~"):
        return ""
    return v


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """The flat subset this unit reads: scalars, flow lists, block lists. A
    nested mapping's children are skipped and the key reads `True` (present).
    Good enough for keys a writer emits flat; never used to WRITE."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    nl = text.find("\n", end + 4)
    block, body = text[4:end], (text[nl + 1 :] if nl != -1 else "")
    fm: dict = {}
    key = None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t" or line.startswith("- "):
            item = line.strip()
            if key and item.startswith("- "):
                if not isinstance(fm.get(key), list):
                    fm[key] = []
                fm[key].append(_scalar(item[2:]))
            elif key and not isinstance(fm.get(key), list):
                fm[key] = True
            continue
        k, sep, v = line.partition(":")
        if not sep:
            continue
        key = k.strip()
        fm[key] = _scalar(v) if v.strip() else ""
    return fm, body


def as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def as_int(value) -> int | None:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        pass
    m = re.match(r"^\s*([\d.]+)\s*([kKmM])\s*$", str(value or ""))
    if m:
        return int(float(m.group(1)) * (1000 if m.group(2).lower() == "k" else 1_000_000))
    return None


def valid_day(value) -> str | None:
    s = str(value or "")
    return s[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", s) else None


# ------------------------------------------------------------------ the catalog


def wiki_root() -> Path:
    """`run` starts a script at the wiki root and exports `LLM_WIKI_ROOT`. A
    jail need not let the root itself be listed, so nothing here looks for
    `.llm-wiki.toml`."""
    return Path(os.environ.get("LLM_WIKI_ROOT") or Path.cwd())


def repo_record(path: Path, root: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm, body = parse_frontmatter(text)
    m = REPO_URL.match(str(fm.get("resource") or "").strip())
    if fm.get("type") not in ("repo", "clip") or not m:
        return None
    tags = [t.lower() for t in as_list(fm.get("tags"))]
    via = as_list(fm.get("gh_via"))
    stars, prev = as_int(fm.get("gh_stars")), as_int(fm.get("gh_stars_prev"))
    summary = ""
    sm = re.search(r"^> \[!summary\]\s*\n((?:>.*\n?)+)", body, re.M)
    if sm:
        summary = " ".join(l.lstrip("> ").strip() for l in sm.group(1).splitlines()).strip()
    uses = re.search(r"^## What it's for\s*\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    return {
        "path": path.relative_to(root).as_posix(),
        "page": path.stem,
        "repo": f"{m.group(1)}/{m.group(2)}",
        "url": f"https://github.com/{m.group(1)}/{m.group(2)}",
        "type": fm.get("type"),
        "status": fm.get("status") or "",
        "description": str(fm.get("description") or "").strip(),
        "summary": summary,
        "use_for": [l[2:].strip() for l in (uses.group(1).splitlines() if uses else []) if l.startswith("- ")],
        "tags": tags,
        "categories": [t for t in tags if t not in SIGNAL_TAGS],
        "stars": stars,
        "stars_prev": prev,
        "stars_prev_at": valid_day(fm.get("gh_stars_prev_at")),
        "seen": valid_day(fm.get("gh_seen")),
        "first_seen": valid_day(fm.get("gh_first_seen")),
        "starred_at": valid_day(fm.get("gh_starred_at")),
        "pushed": valid_day(fm.get("gh_pushed")),
        "language": str(fm.get("gh_language") or ""),
        "topics": as_list(fm.get("gh_topics")),
        "archived": str(fm.get("gh_archived")).lower() == "true",
        "via": via,
        "starred": "gh-starred" in tags or any(v.startswith("stars:") for v in via) or bool(valid_day(fm.get("gh_starred_at"))),
        "clipped": "gh-clipped" in tags or fm.get("type") == "clip",
        "watched": "gh-watched" in tags or any(not v.startswith("stars:") for v in via),
        "signals": [t for t in tags if t in SIGNAL_TAGS],
    }


def load_catalog(root: Path, repos: str, extra_dirs=("sources/clips",)) -> list[dict]:
    """Every repo page under `repos`, plus GitHub-repo clips left elsewhere
    (an older clip in `sources/clips/`) — one record per repo, the `repos`
    page winning."""
    by_repo: dict[str, dict] = {}
    for base in (repos, *extra_dirs):
        d = root / base
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.md")):
            if "_versions" in path.parts or path.name == "index.md":
                continue
            rec = repo_record(path, root)
            if rec and rec["repo"].lower() not in by_repo:
                by_repo[rec["repo"].lower()] = rec
    return list(by_repo.values())


# ------------------------------------------------------------------ ranking


def score(rec: dict, w: dict, today: str) -> float:
    s = w["stars"] * math.log10((rec["stars"] or 0) + 1)
    s += w["starred"] * rec["starred"] + w["clipped"] * rec["clipped"] + w["watched"] * rec["watched"]
    if rec["pushed"] and days_since(rec["pushed"], today) <= w["recent_days"]:
        s += w["recent"]
    if rec["archived"]:
        s += w["archived"]
    gain = jump(rec)
    if gain > 0:
        s += w["jump"] * math.log10(gain + 1)
    return round(s, 2)


def jump(rec: dict) -> int:
    if rec["stars"] is None or rec["stars_prev"] is None:
        return 0
    return rec["stars"] - rec["stars_prev"]


def days_since(day: str, today: str) -> int:
    a = time.mktime(time.strptime(day, "%Y-%m-%d"))
    b = time.mktime(time.strptime(today, "%Y-%m-%d"))
    return int((b - a) // 86400)


def matches(rec: dict, flt: dict) -> bool:
    tags = set(rec["tags"])
    if any(t.lower() not in tags for t in flt.get("tags_all") or []):
        return False
    any_tags = [t.lower() for t in flt.get("tags_any") or []]
    if any_tags and not tags.intersection(any_tags):
        return False
    if any(t.lower() in tags for t in flt.get("tags_none") or []):
        return False
    if flt.get("via_prefix") and not any(v.startswith(flt["via_prefix"]) for v in rec["via"]):
        return False
    if flt.get("starred") is not None and rec["starred"] != flt["starred"]:
        return False
    if flt.get("min_stars") and (rec["stars"] or 0) < int(flt["min_stars"]):
        return False
    if not flt.get("include_archived", True) and rec["archived"]:
        return False
    words = [w for w in re.split(r"\W+", str(flt.get("text") or "").lower()) if len(w) > 2]
    if words:
        hay = " ".join([rec["repo"], rec["description"], rec["summary"], " ".join(rec["use_for"]), " ".join(rec["topics"]), " ".join(rec["tags"])]).lower()
        need = len(words) if flt.get("all_words") else max(1, math.ceil(len(words) / 2))
        if sum(1 for w in words if w in hay) < need:
            return False
    return True


SORTS = {
    "score": lambda r: -r["_score"],
    "stars": lambda r: -(r["stars"] or 0),
    "starred": lambda r: -int((r["starred_at"] or "0000-00-00").replace("-", "")),
    "pushed": lambda r: -int((r["pushed"] or "0000-00-00").replace("-", "")),
    "jump": lambda r: -jump(r),
    "first_seen": lambda r: -int((r["first_seen"] or "0000-00-00").replace("-", "")),
    "name": lambda r: r["repo"].lower(),
}


def ranked(records, flt, sort, limit, weights, today):
    rows = [dict(r, _score=score(r, weights, today)) for r in records if matches(r, flt)]
    rows.sort(key=lambda r: (SORTS[sort](r), r["repo"].lower()))
    return rows[:limit] if limit else rows


# ------------------------------------------------------------------ rendering


def short(n) -> str:
    if n is None:
        return "?"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def how(rec: dict) -> str:
    bits = []
    if rec["starred"]:
        bits.append("starred")
    if rec["clipped"]:
        bits.append("clipped")
    if rec["watched"]:
        bits.append("watched")
    return ", ".join(bits)


def cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "\\|")


def link(rec: dict, in_table=False) -> str:
    # Inside a table the alias pipe must be escaped, or it splits the cell.
    sep = "\\|" if in_table else "|"
    return f"[[{rec['page']}{sep}{rec['repo']}]]"


def render_rows(rows, fmt: str, show_jump=False) -> str:
    if not rows:
        return "*(none yet)*"
    if fmt == "table":
        head = "| Repo | What | ★ | " + ("Δ★ | " if show_jump else "") + "Lang | Last push | How |"
        sep = "| :-- | :-- | --: | " + ("--: | " if show_jump else "") + ":-- | :-- | :-- |"
        lines = [head, sep]
        for r in rows:
            d = f"+{short(jump(r))} | " if show_jump else ""
            lines.append(f"| {link(r, in_table=True)} | {cell(r['description'])} | {short(r['stars'])} | {d}{cell(r['language'])} | {r['pushed'] or ''} | {how(r)} |")
        return "\n".join(lines)
    out = []
    for r in rows:
        bits = [f"★ {short(r['stars'])}"]
        if show_jump and jump(r) > 0:
            bits.append(f"+{short(jump(r))} since {r['stars_prev_at']}")
        if how(r):
            bits.append(how(r))
        out.append(f"- {link(r)} — {cell(r['description']) or '(no description)'} · {' · '.join(bits)}")
    return "\n".join(out)


def list_body(intro: str, rows, fmt, today, total, show_jump=False) -> str:
    return (
        f"{intro}\n\n"
        f"{len(rows)} of {total} repo pages · generated {today} by the channel-github routine — "
        f"do not edit by hand; star counts are as of each repo page's `gh_seen`.\n\n"
        f"{render_rows(rows, fmt, show_jump)}\n"
    )


# ------------------------------------------------------------------ config


def load_config() -> dict:
    try:
        cfg = json.loads(LISTS_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"{LISTS_JSON}: {e}")
    cfg.setdefault("repos", "sources/github")
    cfg.setdefault("also", ["sources/clips"])
    cfg["weights"] = {**DEFAULT_WEIGHTS, **(cfg.get("weights") or {})}
    return cfg


def build_lists(cfg: dict, records: list[dict], today: str) -> list[tuple[str, str, str]]:
    """`[(title, description, body)]` for every list the config declares."""
    w, out = cfg["weights"], []
    total = len(records)
    for spec in cfg.get("lists") or []:
        if spec.get("enabled") is False:
            continue
        fmt = spec.get("format", "compact")
        title = spec.get("title") or f"GitHub list — {spec['name']}"
        if spec.get("kind") == "whats-new":
            window = int(spec.get("window_days", 30))
            min_jump = int(spec.get("min_jump", 1))
            movers = [
                r for r in records if jump(r) >= min_jump and r["seen"] and days_since(r["seen"], today) <= window
            ]
            fresh = [
                r for r in records if r["first_seen"] and days_since(r["first_seen"], today) <= window and r not in movers
            ]
            movers.sort(key=lambda r: (-jump(r), r["repo"].lower()))
            fresh = ranked(fresh, {}, "score", 0, w, today)
            limit = int(spec.get("limit", 50))
            body = (
                f"Repos that jumped in stars, and repos new to the wiki, in the last {window} days.\n\n"
                f"generated {today} by the channel-github routine — do not edit by hand.\n\n"
                f"## Jumped\n\n{render_rows(movers[:limit], fmt, show_jump=True)}\n\n"
                f"## New to the wiki\n\n{render_rows(fresh[:limit], fmt)}\n"
            )
            out.append((title, f"GitHub repos that gained stars or joined the wiki in the last {window} days.", body))
            continue
        rows = ranked(records, spec.get("filter") or {}, spec.get("sort", "score"), int(spec.get("limit", 0)), w, today)
        intro = spec.get("intro") or f"GitHub repos: {spec['name']}."
        out.append((title, spec.get("description") or intro, list_body(intro, rows, fmt, today, total)))
    bc = cfg.get("by_category") or {}
    if bc.get("enabled"):
        counts: dict[str, int] = {}
        for r in records:
            for c in r["categories"]:
                counts[c] = counts.get(c, 0) + 1
        for cat in sorted(c for c, n in counts.items() if n >= int(bc.get("min", 3))):
            rows = ranked(records, {"tags_all": [cat]}, bc.get("sort", "score"), int(bc.get("limit", 0)), w, today)
            title = bc.get("title", "GitHub list — {category}").replace("{category}", cat)
            intro = f"GitHub repos in the `{cat}` category, ranked by score (stars, starred, clipped, recent activity)."
            out.append((title, f"GitHub repos in the {cat} category, ranked.", list_body(intro, rows, bc.get("format", "compact"), today, total)))
    return out


# ------------------------------------------------------------------ commands


def today_utc() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def cmd_census(a):
    root = wiki_root()
    tags, areas, types = {}, {}, {}
    for base in ("wiki", "sources"):
        for path in (root / base).rglob("*.md") if (root / base).is_dir() else []:
            if "_versions" in path.parts:
                continue
            try:
                fm, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            for t in as_list(fm.get("tags")):
                tags[t.lower()] = tags.get(t.lower(), 0) + 1
            for ar in as_list(fm.get("areas")):
                areas[ar] = areas.get(ar, 0) + 1
            if fm.get("type"):
                types[str(fm["type"])] = types.get(str(fm["type"]), 0) + 1
    cfg = load_config()
    records = load_catalog(root, cfg["repos"], cfg["also"])
    cats: dict[str, int] = {}
    topics: dict[str, int] = {}
    for r in records:
        for c in r["categories"]:
            cats[c] = cats.get(c, 0) + 1
        for t in r["topics"]:
            topics[t] = topics.get(t, 0) + 1
    top = lambda d, n: dict(sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n])
    hubs = sorted(p.stem for p in (root / "wiki" / "areas").glob("*.md") if p.name != "index.md") if (root / "wiki/areas").is_dir() else []
    print(json.dumps({"tags": top(tags, a.top), "areas": top(areas, a.top), "area_hubs": hubs, "types": types,
                      "repo_pages": len(records), "repo_categories": top(cats, a.top), "repo_topics": top(topics, a.top)}, indent=1))


def cmd_scan(a):
    root = wiki_root()
    cfg = load_config()
    print(json.dumps(load_catalog(root, cfg["repos"], cfg["also"]), indent=1, ensure_ascii=False))


def read_paths(src: str) -> set[str]:
    text = sys.stdin.read() if src == "-" else Path(src).read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return {l.strip().split(":")[0] for l in text.splitlines() if l.strip()}
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("path", "source_path", "locator") and isinstance(v, str):
                    found.add(v.split(":")[0])
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(data)
    return found


def cmd_rank(a):
    root = wiki_root()
    cfg = load_config()
    records = load_catalog(root, cfg["repos"], cfg["also"])
    if a.paths_from:
        keep = read_paths(a.paths_from)
        records = [r for r in records if r["path"] in keep]
    flt = {"tags_all": a.tag or [], "tags_any": [t for x in a.any_tag or [] for t in x.split(",")], "text": a.text,
           "starred": True if a.starred else None, "min_stars": a.min_stars, "all_words": a.all_words}
    rows = ranked(records, flt, a.sort, a.limit, cfg["weights"], today_utc())
    if a.format == "json":
        print(json.dumps([{k: v for k, v in r.items()} for r in rows], indent=1, ensure_ascii=False))
    else:
        print(render_rows(rows, a.format))
        print(f"\n{len(rows)} shown · {len(records)} candidate repo pages · sort={a.sort}")


def cmd_preview(a):
    root = wiki_root()
    cfg = load_config()
    built = build_lists(cfg, load_catalog(root, cfg["repos"], cfg["also"]), today_utc())
    for title, _desc, body in built:
        if not a.only or a.only.lower() in title.lower():
            print(f"=== {title}\n{body}")


def cmd_pending(a):
    root = wiki_root()
    cfg = load_config()
    rows = [r for r in load_catalog(root, cfg["repos"], cfg["also"]) if r["stars"] is None or r["seen"] is None]
    print(json.dumps({"select": ",".join(f"repo:{r['repo']}" for r in rows), "pages": [r["path"] for r in rows]}, indent=1))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="catalog.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("census")
    c.add_argument("--top", type=int, default=60)
    sub.add_parser("scan")
    r = sub.add_parser("rank")
    r.add_argument("--tag", action="append", help="must carry this tag (repeat to AND)")
    r.add_argument("--any-tag", action="append", help="comma-joined: carries any of these")
    r.add_argument("--text", help="words matched against name, description, summary, uses, topics, tags")
    r.add_argument("--all-words", action="store_true", help="every --text word must match (default: half)")
    r.add_argument("--starred", action="store_true", help="only repos the operator starred")
    r.add_argument("--min-stars", type=int)
    r.add_argument("--paths-from", help="file (or -) of candidate paths: `search query --json` output or one per line")
    r.add_argument("--sort", choices=sorted(SORTS), default="score")
    r.add_argument("--limit", type=int, default=25)
    r.add_argument("--format", choices=("table", "compact", "json"), default="table")
    v = sub.add_parser("preview")
    v.add_argument("--only", help="only the list pages whose title contains this")
    sub.add_parser("pending")
    a = p.parse_args(argv)
    {"census": cmd_census, "scan": cmd_scan, "rank": cmd_rank, "preview": cmd_preview, "pending": cmd_pending}[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
