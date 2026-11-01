#!/usr/bin/env python3
"""A course harvest made readable: split into one capture per item, then one page per capture.

    bbnotes.py split  <harvest dir> --out <items dir>      one capture dir per item, each with capture.json
    bbnotes.py render <capture dir> [--out <file>]         that capture's page(s) as JSON: title, type, published, body
    bbnotes.py notes  <harvest dir> --out <dir>            split and render every capture into <dir>/<title>.md

`harvest.py` runs `split` on what `bb.py harvest` wrote and posts each capture
dir as `captured=`; `process.py` runs `render` on one capture and writes its
page. `notes` is the same two steps by hand, for a harvest taken outside a
job: each note carries `published`, `type` and `course` frontmatter and can be
dropped into `sources/`.

The captures, by `kind` in capture.json:

| kind | body | page |
| :--- | :--- | :--- |
| `course` | `record.json` | the outline, the gradebook with due dates, points and the student's grades, the calendar, off-site links |
| `item` | `record.json` | one content item with a body or instructions: its text, due date, points and grade |
| `file` | the file itself | a pdf, slide deck, Word file or html page an item attaches, embeds or links, as text |
| `video` | the media file | the transcript beside it (`.transcript.webvtt`, or a caption `.vtt`); the transcribe stage writes one where none came |
| `announcement` | `record.json` | one announcement |
| `discussion` | `record.json` | one board: its prompt, then every post by author and date, split into parts past `PART_BYTES` |

Plain `.py`, no PEP 723 block: a script stage runs under the ops interpreter,
which carries `pypdf`. Everything else here is the standard library; without
`pypdf` a pdf's page says its text was not extracted.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

CAPTURE = "capture.json"
RECORD = "record.json"
MEDIA = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".mp3", ".m4a", ".wav"}
DOCUMENTS = {".pdf", ".pptx", ".docx", ".html", ".htm", ".txt", ".md"}
TRANSCRIPT = ".transcript.webvtt"
WRAPPER = re.compile(r"^UNSAFE_HTML_", re.I)
# A discussion page past this many bytes continues in a part of its own: a 980-post board is one source no reader finishes.
PART_BYTES = 60_000
TITLE_MAX = 150
CONTAINERS = {"resource/x-bb-folder", "resource/x-bb-lesson"}
SHORT_HANDLER = {
    "resource/x-bb-document": "document",
    "resource/x-bb-file": "file",
    "resource/x-bb-externallink": "link",
    "resource/x-bb-courselink": "course link",
    "resource/x-bb-blti-link": "LTI tool",
    "resource/x-bb-asmt-test-link": "assignment",
    "resource/x-bb-folder": "folder",
    "resource/x-bb-lesson": "lesson",
}


# ---------------------------------------------------------------- text


class _Text(HTMLParser):
    """HTML to markdown-ish text: headings, paragraphs, lists, bold, links, table rows. Scripts, styles and iframes drop."""

    BLOCK = {"p", "div", "section", "article", "header", "footer", "blockquote", "tr", "table", "ul", "ol", "br", "hr"}
    SKIP = {"script", "style", "iframe", "noscript", "head", "title"}

    def __init__(self, shift: int):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.shift = shift
        self.href: list[str | None] = []
        self.link_text: list[int] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if self.skip:
            return
        if re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + HEADING + "#" * min(6, int(tag[1]) + self.shift) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag == "a":
            self.href.append(dict(attrs).get("href"))
            self.link_text.append(len(self.out))
        elif tag in self.BLOCK:
            self.out.append("\n\n" if tag != "br" else "\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK:
            self.out.append("\n\n")
        elif tag in ("strong", "b"):
            self.out.append("**")
        elif tag == "a" and self.href:
            href, start = self.href.pop(), self.link_text.pop()
            text = "".join(self.out[start:]).strip()
            if href and href.startswith(("http://", "https://", "mailto:")) and href.rstrip("/") not in text:
                self.out.append(f" ({href})")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))


# Marks a heading this parser made, so `html_text` can tell it from a venue line that starts with `#`.
HEADING = "\x00"


def guard(line: str) -> str:
    """A venue line that would read as markup or a wikilink, made plain."""
    line = line.replace("[[", "[\\[").replace("]]", "]\\]")
    if re.match(r"^\s*(#|---|===|```|>)", line):
        line = "\\" + line.lstrip()
    return line


def tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\xa0", " ").splitlines()]
    out: list[str] = []
    for ln in lines:
        ln = re.sub(r"\*\*\s*\*\*", "", ln)
        ln = re.sub(r"[ \t]{2,}", " ", ln).strip()
        if ln in ("**", "|", "- "):
            ln = ""
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


def html_text(markup: str | None, shift: int = 1) -> str:
    """`shift` moves the venue's headings below the page's own H1."""
    if not markup:
        return ""
    p = _Text(shift)
    p.feed(markup)
    p.close()
    text = tidy("".join(p.out))
    return "\n".join(ln[1:].replace(HEADING, "") if ln.startswith(HEADING) else guard(ln.replace(HEADING, "")) for ln in text.splitlines())


def plain(text: str) -> str:
    return tidy("\n".join(guard(ln) for ln in text.splitlines()))


def pdf_text(path: Path) -> tuple[str, str | None]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf is not installed, so the pdf's text was not extracted"
    import logging

    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            # Layout mode keeps a numbered list's number on its line; the plain mode breaks a line per text run.
            try:
                pages.append(page.extract_text(extraction_mode="layout") or "")
            except Exception:  # noqa: BLE001
                pages.append(page.extract_text() or "")
    except Exception as exc:  # noqa: BLE001 - a broken pdf is one page's problem, never the run's
        return "", f"pypdf could not read it ({type(exc).__name__})"
    pages = [unlayout(p) for p in pages]
    if not any(pages):
        return "", "the pdf carries no text layer (a scan)"
    return plain("\n\n".join(p for p in pages if p)), None


def unlayout(text: str) -> str:
    """Layout text as lines a reader quotes: margins gone, a table row's column gaps as ` | `, a lone gap as a space."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        gaps = re.findall(r"\S {3,}\S", line)
        line = re.sub(r" {3,}", " | " if len(gaps) >= 2 else " ", line)
        out.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _xml_texts(data: bytes, para: str, run: str) -> list[str]:
    root = ElementTree.fromstring(data)
    out = []
    for p in root.iter(para):
        words = "".join(t.text or "" for t in p.iter(run)).strip()
        if words:
            out.append(words)
    return out


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def office_text(path: Path) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if path.suffix.lower() == ".docx":
                return plain("\n\n".join(_xml_texts(z.read("word/document.xml"), f"{W}p", f"{W}t"))), None
            def num(n):
                return int(re.search(r"(\d+)\.xml$", n).group(1))
            slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=num)
            notes = {num(n): n for n in names if re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", n)}
            parts = []
            for n in slides:
                words = _xml_texts(z.read(n), f"{A}p", f"{A}t")
                said = _xml_texts(z.read(notes[num(n)]), f"{A}p", f"{A}t") if num(n) in notes else []
                said = [s for s in said if not s.isdigit()]
                if words or said:
                    parts.append(f"### Slide {num(n)}\n\n" + plain("\n".join(words)) + (("\n\nSpeaker notes: " + plain(" ".join(said))) if said else ""))
            return "\n\n".join(parts), None
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as exc:
        return "", f"not a readable {path.suffix} ({type(exc).__name__})"


def file_text(path: Path) -> tuple[str, str | None]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return pdf_text(path)
    if suffix in (".pptx", ".docx"):
        return office_text(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in (".html", ".htm"):
        return html_text(raw), None
    return plain(raw), None


CUE_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?[.,]\d{3}\s+-->")


def vtt_text(path: Path) -> str:
    """A caption track's words, in paragraphs: timings, cue numbers, NOTE blocks and repeated auto-caption lines dropped."""
    words: list[str] = []
    note = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if raw.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            note = raw.startswith(("NOTE", "STYLE", "REGION"))
            continue
        if not line:
            note = False
            continue
        if note or CUE_TIME.match(line) or line.isdigit():
            continue
        line = html.unescape(line)
        if words and (line == words[-1] or words[-1].endswith(line)):
            continue
        words.append(line)
    paras, cur = [], ""
    for w in words:
        cur = f"{cur} {w}".strip()
        if len(cur) > 600 and cur[-1:] in ".?!":
            paras.append(cur)
            cur = ""
    if cur:
        paras.append(cur)
    return "\n\n".join(guard(p) for p in paras)


def transcript_of(media: Path) -> tuple[Path | None, str]:
    """The words beside a media file: the transcribe stage's own, else an English caption track, else any."""
    own = media.with_name(media.stem + TRANSCRIPT)
    if own.is_file():
        return own, "transcribed"
    tracks = sorted(p for p in media.parent.glob(f"{glob_escape(media.stem)}*.vtt") if p.is_file())
    tracks += sorted(p for p in (media.parent / "captions").glob("*.vtt") if p.is_file())
    for pick in (lambda p: ".en." in p.name and "orig" not in p.name, lambda p: ".en" in p.name, lambda p: True):
        for p in tracks:
            if pick(p):
                return p, "captions"
    return None, ""


def glob_escape(text: str) -> str:
    return re.sub(r"([*?\[\]])", r"[\1]", text)


# ---------------------------------------------------------------- names and dates


def day(stamp: str | None) -> str | None:
    found = re.match(r"\d{4}-\d{2}-\d{2}", stamp or "")
    return found.group(0) if found else None


# The zone due dates read in (`--tz`, a job's `timezone` option). Blackboard stores UTC: a 11:59 PM Central due date is 04:59 or 05:59 UTC the next day.
ZONE: list = [timezone.utc]


def set_zone(name: str | None) -> None:
    if name:
        from zoneinfo import ZoneInfo

        ZONE[0] = ZoneInfo(name)


def when(stamp: str | None) -> str:
    """A UTC stamp as the date, weekday and minute a reader sees, in `ZONE`."""
    if not stamp:
        return ""
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return stamp
    local = t.astimezone(ZONE[0])
    return local.strftime("%a %Y-%m-%d %I:%M %p %Z").replace(" 0", " ", 1) if ZONE[0] is not timezone.utc else t.strftime("%a %Y-%m-%d %H:%M UTC")


def safe_title(text: str) -> str:
    text = re.sub(r"[\\/:*?\"<>|#^\[\]]", " ", text).replace("'", "’")
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text[:TITLE_MAX].rstrip(" .") or "untitled"


def course_code(course: dict) -> str:
    """`PSY 2301-21.01.01-2B27-S3, Abnormal Psychology` reads as `PSY 2301`; a course with no code keeps its name."""
    name = (course or {}).get("name") or (course or {}).get("courseId") or "course"
    found = re.match(r"\s*([A-Z]{2,5})\s?-?(\d{3,4}[A-Z]?)\b", name) or re.match(r"\s*([A-Z]{2,5})(\d{3,4})", (course or {}).get("courseId") or "")
    return f"{found.group(1)} {found.group(2)}" if found else name.split(",")[0].strip()


def course_title(course: dict) -> str:
    name = (course or {}).get("name") or ""
    tail = name.split(",", 1)[1].strip() if "," in name else ""
    code = course_code(course)
    return f"{code} {tail}".strip() if tail and tail not in code else code


def fingerprint(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def file_print(path: Path) -> str:
    st = path.stat()
    with path.open("rb") as f:
        head = f.read(1 << 20)
    return fingerprint(st.st_size, head)


def item_title(item: dict) -> str:
    """An Ultra document's body item is titled `ultraDocumentBody`; the folder above it carries the name a person gave it."""
    title = (item.get("title") or "").strip()
    if title.lower() == "ultradocumentbody" or not title:
        parts = [p for p in (item.get("path") or "").split("/") if p and p.lower() != "ultradocumentbody"]
        return parts[-1] if parts else "untitled"
    return title


def person(post: dict) -> str:
    name = " ".join(x for x in (post.get("givenName"), post.get("familyName")) if x).strip()
    return name or "the instructor"


# ---------------------------------------------------------------- split


def _load(harvest: Path, name: str, default):
    path = harvest / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return default


def _place(src: Path, dest: Path) -> None:
    """A harvested file into its capture: a hard link where the filesystem allows, so a video is never stored twice."""
    if dest.exists():
        if dest.stat().st_size == src.stat().st_size:
            return
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)


class _Split:
    def __init__(self, harvest: Path, out: Path, fetched_at: str):
        self.h, self.out, self.fetched_at = harvest, out, fetched_at
        self.course = _load(harvest, "course.json", {}) or {}
        self.code = course_code(self.course)
        self.cid = self.course.get("id") or harvest.name
        self.titles: set[str] = set()
        self.dirs: list[Path] = []

    def title(self, text: str) -> str:
        base = safe_title(text)
        name, n = base, 2
        while name.lower() in self.titles:
            name = f"{base[: TITLE_MAX - 6]} ({n})"
            n += 1
        self.titles.add(name.lower())
        return name

    def write(self, key: str, kind: str, title: str, published: str | None, *, record=None, body_file: Path | None = None, extra=None, facts=None) -> Path:
        d = self.out / key
        d.mkdir(parents=True, exist_ok=True)
        if record is not None:
            text = json.dumps(record, indent=1, ensure_ascii=False, default=str)
            (d / RECORD).write_text(text + "\n", encoding="utf-8")
            body, printed = RECORD, fingerprint(text)
        else:
            _place(body_file, d / body_file.name)
            body, printed = body_file.name, file_print(body_file)
            for words in extra or ():
                _place(words, d / words.name)
                printed = fingerprint(printed, file_print(words))
        cap = {
            "v": 1,
            "slug": None,
            "item": f"blackboard:{self.cid}/{key}",
            "title": self.title(title),
            "body": body,
            "fetched_at": self.fetched_at,
            "kind": kind,
            "course": self.code,
            "course_name": self.course.get("name"),
            "published": published,
            "fingerprint": printed,
            **({"facts": facts} if facts else {}),
        }
        (d / CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        self.dirs.append(d)
        return d

    def run(self) -> list[Path]:
        h = self.h
        contents = _load(h, "contents.json", [])
        files = _load(h, "files.json", [])
        columns = _load(h, "gradebook-columns.json", [])
        grades = {g.get("columnId"): g for g in _load(h, "my-grades.json", [])}
        by_content = {c.get("contentId"): c for c in columns if c.get("contentId")}
        by_id = {c.get("id"): c for c in columns}
        items = {c["id"]: c for c in contents}
        files_of: dict[str, list[dict]] = {}
        for f in files:
            files_of.setdefault(f.get("item"), []).append(f)

        def grade_facts(col: dict | None) -> dict:
            if not col:
                return {}
            g = grades.get(col.get("id")) or {}
            shown = g.get("displayGrade") or {}
            return {
                "due": (col.get("grading") or {}).get("due"),
                "points": (col.get("score") or {}).get("possible"),
                "column": col.get("name"),
                "status": g.get("status"),
                "score": shown.get("score"),
                "feedback": g.get("feedback"),
            }

        # One page per document or video a content item carries; the item's own page lists them.
        carried: dict[str, list[str]] = {}
        for item_id, rows in files_of.items():
            owner = items.get(item_id)
            if owner is None:
                continue
            for f in rows:
                src = h / f["path"]
                suffix = src.suffix.lower()
                if not src.is_file() or (suffix not in MEDIA and suffix not in DOCUMENTS):
                    continue
                if suffix in (".html", ".htm") and WRAPPER.match(src.name):
                    continue
                key = f"{'video' if suffix in MEDIA else 'file'}-{fingerprint(f['path'])[:12]}"
                where = {"where": owner.get("path"), "owner": item_title(owner), "posted": owner.get("created"), "updated": owner.get("modified")}
                if suffix in MEDIA:
                    words, _how = transcript_of(src)
                    title = f"{self.code} — {item_title(owner)} — {src.stem} (video)"
                    self.write(key, "video", title, day(owner.get("modified")), body_file=src, extra=[words] if words else None, facts=where)
                else:
                    if suffix in (".html", ".htm") and not html_text(src.read_text(encoding="utf-8", errors="replace")):
                        continue
                    alone = owner.get("handler") == "resource/x-bb-file"
                    title = f"{self.code} — {item_title(owner)}" + ("" if alone else f" — {src.name}")
                    self.write(key, "file", title, day(owner.get("modified")), body_file=src, facts=where)
                carried.setdefault(item_id, []).append(self.dirs[-1].name)

        # Media a person fetched beside the harvest (`external/`, yt-dlp): a video capture each.
        for src in sorted((h / "external").glob("*")) if (h / "external").is_dir() else []:
            if src.suffix.lower() in MEDIA and src.is_file():
                words, _how = transcript_of(src)
                stem = re.sub(r" \[[^\]]+\]$", "", src.stem)
                title = f"{self.code} — {stem} (video)"
                self.write(f"video-{fingerprint('external/' + src.name)[:12]}", "video", title, None, body_file=src, extra=[words] if words else None)

        for item in contents:
            raw = item.get("raw") or {}
            ch = raw.get("contentHandler") or {}
            body_path = h / "bodies" / f"{item['id']}.html"
            body = body_path.read_text(encoding="utf-8", errors="replace") if body_path.is_file() else ""
            wrappers = [h / f["path"] for f in files_of.get(item["id"], []) if WRAPPER.match(Path(f["path"]).name) and (h / f["path"]).is_file()]
            wrapped = "\n\n".join(html_text(p.read_text(encoding="utf-8", errors="replace")) for p in wrappers)
            text = html_text(body)
            instructions = html_text(ch.get("instructions") or "")
            description = raw.get("description") or ""
            col = by_id.get(ch.get("gradeColumnId")) or by_content.get(item["id"])
            if description.strip() == (item.get("title") or "").strip():
                description = ""
            if item.get("handler") in CONTAINERS and not (text or wrapped):
                continue
            if not (text or wrapped or instructions or description or col):
                continue  # a bare link is an outline line; what an item carries has pages of its own
            record = {
                "id": item["id"],
                "title": item.get("title"),
                "path": item.get("path"),
                "handler": item.get("handler"),
                "created": item.get("created"),
                "modified": item.get("modified"),
                "available": item.get("available"),
                "syllabus": item.get("syllabus"),
                "url": item.get("url") if (item.get("url") or "").startswith("http") else None,
                "text": text,
                "wrapped": wrapped,
                "instructions": instructions,
                "description": description,
                "grade": grade_facts(col),
                "carries": [self.out / k for k in carried.get(item["id"], [])],
            }
            record["carries"] = [json.loads((p / CAPTURE).read_text())["title"] for p in record["carries"]]
            record["title"] = item_title(item)
            self.write(f"item-{item['id'].strip('_')}", "item", f"{self.code} — {item_title(item)}", day(item.get("modified")), record=record)

        for a in _load(h, "announcements.json", []):
            record = {"id": a.get("id"), "title": a.get("title"), "created": a.get("created"), "modified": a.get("modified"),
                      "shown_from": ((a.get("availability") or {}).get("duration") or {}).get("start"), "text": html_text(a.get("body"))}
            self.write(f"announcement-{str(a.get('id')).strip('_')}", "announcement", f"{self.code} announcement — {a.get('title')}",
                       day(a.get("modified") or a.get("created")), record=record)

        for d in _load(h, "discussions.json", []):
            posts = _load(h, f"discussions/{d.get('id')}.json", [])
            topic = d.get("topic") if isinstance(d.get("topic"), dict) else {}
            if not posts and not html_text(topic.get("body")):
                continue
            col = by_id.get(d.get("gradebookColumnId"))
            posts = [p for p in posts if p.get("status", "Published") == "Published"]
            last = max((p.get("postDate") or p.get("createdDate") or "" for p in posts), default="") or d.get("modifiedDate")
            record = {"id": d.get("id"), "title": d.get("title"), "prompt": html_text(topic.get("body")), "grade": grade_facts(col),
                      "posts": [{"id": p.get("id"), "parent": p.get("parentId"), "thread": p.get("threadId"), "author": person(p),
                                 "posted": p.get("postDate") or p.get("createdDate"), "text": html_text(p.get("body"), shift=2)}
                                for p in posts],
                      "topic_id": topic.get("id")}
            self.write(f"discussion-{str(d.get('id')).strip('_')}", "discussion", f"{self.code} discussion — {d.get('title')}", day(last), record=record)

        outline = [{"path": c.get("path"), "title": c.get("title"), "handler": c.get("handler"), "available": c.get("available"),
                    "url": c.get("url") if (c.get("url") or "").startswith("http") else None} for c in contents]
        record = {
            "course": {k: self.course.get(k) for k in ("id", "courseId", "name", "externalAccessUrl")},
            "term": ((self.course.get("availability") or {}).get("duration") or {}),
            "outline": outline,
            "gradebook": [dict(grade_facts(c), name=c.get("name")) for c in columns],
            "calendar": [{"title": e.get("title"), "start": e.get("start"), "end": e.get("end"),
                          "type": (e.get("dynamicCalendarItemProps") or {}).get("eventType") or e.get("type")} for e in _load(h, "calendar.json", [])],
            "external": [{"url": e.get("url"), "title": e.get("title"), "video": e.get("video"),
                          "item": (items.get(e.get("item")) or {}).get("title")} for e in _load(h, "external.json", [])],
        }
        self.write("course", "course", f"{course_title(self.course)} — course overview", day(self.fetched_at), record=record)
        return self.dirs


def split(harvest: Path, out: Path, fetched_at: str | None = None) -> list[Path]:
    """One capture dir per item under `out`, titles settled across the course; returns them in the order written."""
    stamp = fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _Split(harvest, out, stamp).run()


# ---------------------------------------------------------------- render


def _facts(rows: list[tuple[str, object]]) -> str:
    return "\n".join(f"- {k}: {v}" for k, v in rows if v not in (None, "", []))


def _grade_rows(g: dict) -> list[tuple[str, object]]:
    if not g:
        return []
    score = None
    if g.get("score") is not None:
        score = f"{g['score']:g} of {g['points']:g}" if g.get("points") else f"{g['score']:g}"
    return [("Due", when(g.get("due"))), ("Points possible", f"{g['points']:g}" if g.get("points") else None),
            ("My grade", score), ("Grade status", g.get("status") if g.get("status") not in (None, "Graded") or score is None else None),
            ("Instructor feedback", html_text(g.get("feedback")).replace("\n", " ") if g.get("feedback") else None)]


def _render_item(cap: dict, r: dict) -> list[dict]:
    kind = SHORT_HANDLER.get(r.get("handler"), r.get("handler"))
    head = _facts([("Course", cap.get("course_name")), ("Where", (r.get("path") or "").replace("/", " › ")), ("Kind", kind),
                   ("Syllabus", "yes" if r.get("syllabus") else None), ("Link", r.get("url")),
                   ("Posted", day(r.get("created"))), ("Last updated", day(r.get("modified"))), *_grade_rows(r.get("grade") or {})])
    parts = [f"# {r.get('title')}", head]
    for heading, text in (("Description", r.get("description")), ("Instructions", r.get("instructions")), (None, r.get("text")), (None, r.get("wrapped"))):
        if text:
            parts.append((f"## {heading}\n\n" if heading else "") + (plain(text) if heading == "Description" else text))
    if r.get("carries"):
        parts.append("## Files and videos\n\n" + "\n".join(f"- [[{t}]]" for t in r["carries"]))
    return [{"title": cap["title"], "type": "document", "published": cap.get("published"), "body": "\n\n".join(parts) + "\n"}]


def _render_announcement(cap: dict, r: dict) -> list[dict]:
    head = _facts([("Course", cap.get("course_name")), ("Posted", day(r.get("created"))),
                   ("Last edited", day(r.get("modified")) if day(r.get("modified")) != day(r.get("created")) else None),
                   ("Shown from", day(r.get("shown_from")))])
    return [{"title": cap["title"], "type": "note", "published": cap.get("published"),
             "body": f"# {r.get('title')}\n\n{head}\n\n{r.get('text') or ''}\n"}]


def _render_discussion(cap: dict, r: dict) -> list[dict]:
    posts = r.get("posts") or []
    kids: dict[str | None, list[dict]] = {}
    for p in posts:
        kids.setdefault(p.get("parent"), []).append(p)
    for v in kids.values():
        v.sort(key=lambda p: p.get("posted") or "")
    ids = {p["id"] for p in posts}
    roots = [p for p in posts if p.get("parent") in (None, r.get("topic_id")) or p.get("parent") not in ids]
    roots.sort(key=lambda p: p.get("posted") or "")

    def thread(p: dict, depth: int) -> str:
        label = "Reply from" if depth else "Post from"
        block = f"{'#' * min(6, 3 + depth)} {label} {p['author']}, {when(p.get('posted'))}\n\n{p.get('text') or ''}"
        return "\n\n".join([block] + [thread(c, depth + 1) for c in kids.get(p["id"], [])])

    head = _facts([("Course", cap.get("course_name")), ("Posts", len(posts)), *_grade_rows(r.get("grade") or {})])
    intro = f"# {r.get('title')}\n\n{head}\n\n" + (f"## Prompt\n\n{r['prompt']}\n\n" if r.get("prompt") else "")
    chunks, cur = [], ""
    for p in roots:
        block = thread(p, 0) + "\n\n"
        if cur and len(cur.encode()) + len(block.encode()) > PART_BYTES:
            chunks.append(cur)
            cur = ""
        cur += block
    if cur or not chunks:
        chunks.append(cur)
    out = []
    for n, chunk in enumerate(chunks, 1):
        title = cap["title"] if n == 1 else safe_title(f"{cap['title']} (part {n})")
        lead = intro if n == 1 else f"# {r.get('title')} (part {n} of {len(chunks)})\n\n{_facts([('Course', cap.get('course_name')), ('Continues', f'[[{cap['title']}]]')])}\n\n"
        tail = f"\n\nContinued in [[{safe_title(cap['title'] + f' (part {n + 1})')}]]." if n < len(chunks) else ""
        out.append({"title": title, "type": "note", "published": cap.get("published"),
                    "body": lead + ("## Posts\n\n" if chunk else "") + chunk.rstrip() + tail + "\n"})
    return out


def _render_course(cap: dict, r: dict) -> list[dict]:
    c = r.get("course") or {}
    term = r.get("term") or {}
    parts = [f"# {cap['title'].removesuffix(' — course overview')}",
             _facts([("Course", c.get("name")), ("Course id", c.get("courseId")), ("Term starts", day(term.get("start"))),
                      ("Term ends", day(term.get("end"))), ("Harvested", day(cap.get("fetched_at")))])]
    rows = [g for g in r.get("gradebook") or [] if g.get("name")]
    if rows:
        lines = ["| Graded item | Due | Points | My grade | Feedback |", "| --- | --- | --- | --- | --- |"]
        for g in sorted(rows, key=lambda g: g.get("due") or "9999"):
            score = f"{g['score']:g}" if g.get("score") is not None else (g.get("status") or "")
            fb = html_text(g.get("feedback")).replace("\n", " ").replace("|", "/") if g.get("feedback") else ""
            pts = f"{g['points']:g}" if g.get("points") else ""
            lines.append(f"| {g['name']} | {when(g.get('due'))} | {pts} | {score} | {fb} |")
        parts.append("## Gradebook\n\n" + "\n".join(lines))
    if r.get("calendar"):
        parts.append("## Calendar\n\n" + "\n".join(f"- {when(e.get('start'))}: {e.get('title')} ({e.get('type')})" for e in r["calendar"]))
    outline = [o for o in r.get("outline") or [] if o.get("path")]
    if outline:
        lines = []
        for o in outline:
            depth = o["path"].count("/")
            kind = SHORT_HANDLER.get(o.get("handler"), o.get("handler"))
            hidden = "" if o.get("available") in (None, "Yes", True) else f", {o['available']}"
            lines.append(f"{'  ' * depth}- {o.get('title')} ({kind}{hidden})" + (f" — {o['url']}" if o.get("url") else ""))
        parts.append("## Outline\n\n" + "\n".join(lines))
    ext = [e for e in r.get("external") or [] if e.get("url")]
    if ext:
        parts.append("## Off-site links\n\n" + "\n".join(
            f"- {e.get('title') or e.get('item') or 'link'}{' (video)' if e.get('video') else ''}: {e['url']}" for e in ext))
    return [{"title": cap["title"], "type": "document", "published": cap.get("published"), "body": "\n\n".join(parts) + "\n"}]


def _render_file(cap: dict, path: Path) -> list[dict]:
    text, why = file_text(path)
    head = _facts([("Course", cap.get("course_name")), *_where(cap), ("File", path.name), ("Text", why)])
    title = cap["title"]
    return [{"title": title, "type": "document", "published": cap.get("published"),
             "body": f"# {title.split(' — ', 1)[-1]}\n\n{head}\n\n{text}\n", "problem": why}]


def _where(cap: dict) -> list[tuple[str, object]]:
    f = cap.get("facts") or {}
    return [("Where", (f.get("where") or "").replace("/", " › ")), ("Posted", day(f.get("posted"))), ("Last updated", day(f.get("updated")))]


def _render_video(cap: dict, path: Path, directory: Path) -> list[dict]:
    words, how = transcript_of(directory / path.name)
    body = vtt_text(words) if words else ""
    why = None if body else "no transcript or captions beside the video yet"
    head = _facts([("Course", cap.get("course_name")), *_where(cap), ("Video", path.name),
                   ("Transcript", {"transcribed": "machine transcript", "captions": "the video's own captions"}.get(how) or why)])
    return [{"title": cap["title"], "type": "video", "published": cap.get("published"),
             "body": f"# {cap['title'].split(' — ', 1)[-1]}\n\n{head}\n\n" + (f"## Transcript\n\n{body}\n" if body else ""), "problem": why}]


def render(directory: Path) -> list[dict]:
    """The page(s) one capture makes: `title`, `type`, `published`, `body`, and `problem` where text could not be had."""
    cap = json.loads((directory / CAPTURE).read_text(encoding="utf-8"))
    body = directory / cap["body"]
    kind = cap.get("kind")
    if kind == "file":
        return _render_file(cap, body)
    if kind == "video":
        return _render_video(cap, body, directory)
    record = json.loads(body.read_text(encoding="utf-8"))
    return {"item": _render_item, "announcement": _render_announcement, "discussion": _render_discussion,
            "course": _render_course}[kind](cap, record)


# ---------------------------------------------------------------- cli


def _frontmatter(page: dict, cap: dict) -> str:
    # No `resource`: that is a job's page identity, which `process.py` sets; a dropped note belongs to no job.
    rows = {"type": page["type"], "published": page.get("published"), "course": cap.get("course")}
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in rows.items() if v) + "---\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("split")
    p.add_argument("harvest", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("render")
    p.add_argument("capture", type=Path)
    p.add_argument("--out", type=Path)
    p = sub.add_parser("notes")
    p.add_argument("harvest", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--items", type=Path, help="where the captures go (default: <out>/.captures)")
    for p in sub.choices.values():
        p.add_argument("--tz", help="the zone due dates and post times read in, an IANA name (default UTC)")
    args = ap.parse_args(argv)
    set_zone(args.tz)
    if args.cmd == "split":
        if not (args.harvest / "course.json").is_file():
            print(f"refused: {args.harvest} holds no course.json — not a `bb.py harvest` output", file=sys.stderr)
            return 2
        dirs = split(args.harvest, args.out)
        print(json.dumps([str(d) for d in dirs], indent=1))
        return 0
    if args.cmd == "render":
        pages = render(args.capture)
        text = json.dumps(pages, indent=1, ensure_ascii=False)
        args.out.write_text(text + "\n", encoding="utf-8") if args.out else print(text)
        return 0
    if not (args.harvest / "course.json").is_file():
        print(f"refused: {args.harvest} holds no course.json — not a `bb.py harvest` output", file=sys.stderr)
        return 2
    items = args.items or args.out / ".captures"
    args.out.mkdir(parents=True, exist_ok=True)
    written, problems = 0, []
    for d in split(args.harvest, items):
        cap = json.loads((d / CAPTURE).read_text(encoding="utf-8"))
        for page in render(d):
            (args.out / f"{page['title']}.md").write_text(_frontmatter(page, cap) + page["body"], encoding="utf-8")
            written += 1
            if page.get("problem"):
                problems.append(f"{page['title']}: {page['problem']}")
    print(f"{written} notes -> {args.out}")
    for line in problems:
        print(f"  no text: {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
