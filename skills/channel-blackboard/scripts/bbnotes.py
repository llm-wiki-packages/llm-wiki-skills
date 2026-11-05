#!/usr/bin/env python3
"""A course harvest made readable: split into one capture per item, then one page per capture.

    bbnotes.py split  <harvest dir> --out <items dir>      one capture dir per item, each with capture.json
    bbnotes.py render <capture dir> [--out <file>]         that capture's page(s) as JSON: title, type, published, abstract, body
    bbnotes.py notes  <harvest dir> --out <dir>            split and render every capture into <dir>/<title>.md

`harvest.py` runs `split` on what `bb.py harvest` wrote (placing each new page
by the job's layout options, `layout_of`, and keeping each place in
`placement.json` beside the captures) and posts each capture dir as `captured=`; `process.py` runs `render` on one capture and writes its
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
from collections import Counter
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

CAPTURE = "capture.json"
RECORD = "record.json"
MEDIA = {".mp4", ".m4v", ".mov", ".webm", ".mkv", ".mp3", ".m4a", ".wav"}
DOCUMENTS = {".pdf", ".pptx", ".docx", ".html", ".htm", ".txt", ".md"}
TRANSCRIPT = ".transcript.webvtt"
WRAPPER = re.compile(r"^UNSAFE_HTML_", re.I)
# A discussion page past this many bytes continues in a part of its own: a 980-post board is one source no reader finishes.
PART_BYTES = 60_000
_TITLE_SWAPS = {":": " -", "/": "-", "\\": "-", "|": "-", "?": "", "*": "", '"': "\u2019", "'": "\u2019", "<": "(", ">": ")"}
TITLE_MAX = 120   # characters
# …and a filename is capped in BYTES by the filesystem (255 on ext4/APFS), with `.md` appended:
# 120 characters of CJK is 360 bytes, which `filename_for` lets through and the write then fails on.
TITLE_MAX_BYTES = 200
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
    """A stamp's date as a reader in `ZONE` sees it; a bare date, or one that does not parse, as written."""
    found = re.match(r"\d{4}-\d{2}-\d{2}", stamp or "")
    if not found:
        return None
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return found.group(0)
    if len(stamp) <= 10:
        return found.group(0)
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(ZONE[0]).date().isoformat()


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


def safe_title(text, fallback="Untitled"):
    text = "".join(ch if ch.isprintable() else " " for ch in str(text or ""))  # control chars, newlines, tabs
    for bad, good in _TITLE_SWAPS.items():
        text = text.replace(bad, good)
    text = " ".join(text.split()).lstrip(". ").rstrip(" .")
    cut = text[:TITLE_MAX]
    while len(cut.encode("utf-8")) > TITLE_MAX_BYTES:
        cut = cut[:-1]
    if cut != text:
        text = cut.rstrip(" .-") + "…"
    if text.casefold() == "index":
        # `index.md` is the host's one RESERVED page name (note.py::RESERVED): its page walker skips
        # it, so the page never appears in `known[]` and the item is re-pulled forever.
        text = f"{text} (page)"
    return text or fallback


# What a built `[[link]]` needs beyond the shared title rule: Obsidian reads `#` and `^` inside one
# as a heading or block reference, and a bracket ends it. Look-alikes, so the title still reads.
_LINK_SWAPS = {"#": "\uff03", "^": "\u02c6", "[": "(", "]": ")"}


def page_title(text, fallback="Untitled"):
    """`safe_title` for a page this unit links to: `_LINK_SWAPS` first."""
    text = str(text or "")
    for bad, good in _LINK_SWAPS.items():
        text = text.replace(bad, good)
    return safe_title(text, fallback)


def one_line(text, *, cell: bool = False) -> str:
    """Venue text set in a heading, a list item or a table cell: one line, guarded; in a cell `|` is a look-alike."""
    line = guard(" ".join(str(text if text is not None else "").split()))
    return line.replace("|", "\u00a6") if cell else line


# Meeting hosts whose link carries its passcode in the query string: the overview keeps the room, not the key.
MEETING_HOSTS = re.compile(r"(^|\.)(zoom\.us|zoomgov\.com|teams\.microsoft\.com|teams\.live\.com|meet\.google\.com)$", re.IGNORECASE)


def shown_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    if parts.hostname and MEETING_HOSTS.search(parts.hostname):
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return url


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


# ---------------------------------------------------------------- layout

# In the items directory, beside the captures: where each page was first placed, each module's folder, what left the course.
LEDGER = "placement.json"
# In a removed item's capture: written by process once its page carries `removed`, so a stamp that failed is posted again.
DATED = "dated.json"
# The job's layout options, each with its words; the first is the default. `legacy` is the layout before 0.3.0 (one folder,
# a page per title): a job added before then has no `layout` option, and its pages already stand at their titles.
CHOICES = {"layout": ("legacy", "modules", "flat"), "prefix": ("position", "none"), "backfill": ("changed", "none", "all")}
SECTIONS = {"announcements": "announcements_dir", "discussions": "discussions_dir"}
ALONGSIDE = "alongside"
# `backfill=none` leaves a module's pages alone this long after its last due date: grades and feedback come after it.
FREEZE_GRACE = timedelta(days=7)
# The overview's "Added" section: what was first seen this many days back, the first pull's own excepted.
ADDED_DAYS = 7


def layout_of(options: dict | None) -> dict:
    """The job's layout options, checked; a word that is not one raises `ValueError` naming it."""
    options = options or {}
    out = {}
    for key, words in CHOICES.items():
        word = str(options.get(key) or words[0]).strip().lower()
        if word not in words:
            raise ValueError(f"options.{key}={options.get(key)!r} (one of {', '.join(words)})")
        out[key] = word
    for section, key in SECTIONS.items():
        word = str(options.get(key) or section).strip()
        folder = ALONGSIDE if word.lower() == ALONGSIDE else page_title(word.strip("/"), section)
        if "/" in word.strip("/"):
            raise ValueError(f"options.{key}={word!r} is one folder name, or {ALONGSIDE}")
        out[section] = folder
    depth = str(options.get("depth") or "1").strip()
    if depth != "1":
        raise ValueError(f"options.depth={depth!r}: only 1 (top-level modules, deeper items numbered 03.02) is made yet")
    return out


class Ledger:
    """`placement.json`: read once, written whole through a temporary file, so a pull that dies leaves the last one."""

    def __init__(self, path: Path):
        self.path = path
        loaded = _load(path.parent, path.name, {}) if path.parent.is_dir() else {}
        self.data = loaded if isinstance(loaded, dict) else {}
        self.data.setdefault("v", 1)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)


class _Outline:
    """The content tree by parent id (a title may hold `/`, so never by splitting `path`)."""

    def __init__(self, contents: list[dict]):
        self.rows = {c["id"]: c for c in contents if isinstance(c, dict) and c.get("id")}
        self.order = [c["id"] for c in contents if isinstance(c, dict) and c.get("id")]
        self.kids: dict[str | None, list[str]] = {}
        for cid in self.order:
            self.kids.setdefault(self.parent(cid), []).append(cid)

    def parent(self, cid: str) -> str | None:
        p = (self.rows.get(cid) or {}).get("parent")
        return p if p in self.rows and p != cid else None

    def position(self, cid: str) -> int:
        raw = (self.rows[cid].get("raw") or {}).get("position")
        if isinstance(raw, int) and raw >= 0:
            return raw
        return self.kids.get(self.parent(cid), [cid]).index(cid)

    def title(self, cid: str) -> str:
        return item_title(self.rows[cid])

    def anchor(self, cid: str) -> str:
        """The row a page stands for: an item that is its folder's only child is the folder (Ultra's `ultraDocumentBody`,
        a `Part 1.` folder holding its one document), so it takes the folder's place in the outline."""
        cur = cid
        while True:
            p = self.parent(cur)
            if p is None or self.parent(p) is None or self.rows[p].get("handler") != "resource/x-bb-folder" or len(self.kids.get(p, [])) != 1:
                return cur
            cur = p

    def chain(self, cid: str) -> list[str]:
        """The anchor and every row above it, top first."""
        out, cur = [], self.anchor(cid)
        while cur is not None and cur not in out:
            out.append(cur)
            cur = self.parent(cur)
        return out[::-1]

    def module(self, cid: str | None) -> str | None:
        """The top-level lesson or folder a row sits in; None for a row at the top."""
        if cid not in self.rows:
            return None
        chain = self.chain(cid)
        return chain[0] if len(chain) > 1 and self.rows[chain[0]].get("handler") in CONTAINERS else None

    def modules(self) -> list[str]:
        return [cid for cid in self.kids.get(None, []) if self.rows[cid].get("handler") in CONTAINERS]

    def prefix(self, cid: str) -> str:
        """The row's outline position below its module, one-based and zero-padded: `03`, or `03.02` a level deeper."""
        chain = self.chain(cid)
        below = chain[1:] if self.module(cid) else chain
        return ".".join(f"{self.position(x) + 1:02d}" for x in below) or "00"

    def path(self, cid: str) -> str:
        return " / ".join(self.title(x) for x in self.chain(cid))


ROMAN = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
ORDINAL = re.compile(r"^\s*(?:unit|module|week|part|lesson|chapter|topic|section|session)\s*[-:.]?\s*(\d+|[ivxlc]+)\b", re.I)


def module_order(title: str) -> int | None:
    """`Unit IV` reads 4, `Module 3- Memory` 3, `Part 2.` 2; a title with no number None."""
    found = ORDINAL.match(title or "")
    if not found:
        return None
    word = found.group(1).lower()
    if word.isdigit():
        return int(word)
    total = 0
    for a, b in zip(word, word[1:] + " "):
        n = ROMAN[a]
        total += -n if b in ROMAN and ROMAN[b] > n else n
    return total


def page_kind(handler: str | None, title: str) -> str:
    if handler == "resource/x-bb-asmt-test-link":
        return "assignment"
    if re.search(r"study\s*guide", title or "", re.I):
        return "study-guide"
    if handler == "resource/x-bb-file":
        return "file"
    return "document"


def local_time(stamp: str) -> str:
    """A UTC stamp in `ZONE`, to the minute, with its offset: what a `due` field holds."""
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return stamp
    return t.astimezone(ZONE[0]).isoformat(timespec="minutes")


def _short(title: str, code: str) -> str:
    """A settled title less its course code: the folder carries the course."""
    for lead in (f"{code} — ", f"{code} announcement — ", f"{code} discussion — "):
        if title.startswith(lead):
            return title[len(lead):]
    return title


class _Split:
    def __init__(self, harvest: Path, out: Path, fetched_at: str, course_id: str | None = None, discussions: bool = True,
                 options: dict | None = None):
        self.h, self.out, self.fetched_at, self.discussions = harvest, out, fetched_at, discussions
        self.layout = layout_of(options)
        self.ledger = Ledger(out / LEDGER)
        self.outline = _Outline([])
        self.grade_of: dict[str, dict] = {}
        loaded = _load(harvest, "course.json", {})
        self.course = loaded if isinstance(loaded, dict) else {}
        self.code = course_code(self.course)
        # Every capture's `resource` is built on it: a directory's name would make a second identity for the same course.
        self.cid = self.course.get("id") or course_id
        if not self.cid:
            raise ValueError(f"{harvest / 'course.json'} names no course id, and none was given")
        self.pending: list[dict] = []
        self.dirs: list[Path] = []

    def write(self, key: str, kind: str, title: str, published: str | None, *, record=None, body_file: Path | None = None, extra=None,
              facts=None, under: str | None = None, node: str | None = None, section: str | None = None) -> Path:
        """Stage one capture; `settle` writes it once every title in the course is known. `under` qualifies a shared title."""
        d = self.out / key
        d.mkdir(parents=True, exist_ok=True)
        (d / DATED).unlink(missing_ok=True)  # listed again: a later removal is dated afresh
        printed = None
        if record is None:
            _place(body_file, d / body_file.name)
            printed = file_print(body_file)
            for words in extra or ():
                _place(words, d / words.name)
                printed = fingerprint(printed, file_print(words))
        self.pending.append({"dir": d, "key": key, "kind": kind, "base": page_title(title), "under": under, "published": published,
                             "record": record, "body": RECORD if record is not None else body_file.name, "printed": printed, "facts": facts,
                             "node": node, "section": section})
        self.dirs.append(d)
        return d

    def titles(self) -> dict[str, str]:
        """Each capture's title, the same whatever else the course holds and in whatever order it lists: a title two
        captures share is qualified by the folder above each, and where that is shared too, by the id's tail. Never a count."""
        groups: dict[str, list[dict]] = {}
        for p in self.pending:
            groups.setdefault(p["base"].lower(), []).append(p)
        out = {}
        for group in groups.values():
            if len(group) == 1:
                out[group[0]["key"]] = group[0]["base"]
                continue
            first = {p["key"]: _qualified(p["base"], p["under"]) if p["under"] else None for p in group}
            shared = Counter(t.lower() for t in first.values() if t)
            for p in group:
                t = first[p["key"]]
                out[p["key"]] = t if t and shared[t.lower()] == 1 else _qualified(p["base"], p["key"].rsplit("-", 1)[-1][-8:])
        return out

    def settle(self) -> None:
        titles = self.titles()
        before = {c.parent.name for c in self.out.glob(f"*/{CAPTURE}")}
        placed = self.place(titles)
        self.removals(before, {p["key"] for p in self.pending})
        links = {p["key"]: {"title": titles[p["key"]], "place": placed[p["key"]]["place"],
                            **({"module": placed[p["key"]]["module"]} if placed[p["key"]]["place"] and self.layout["layout"] == "modules"
                               and placed[p["key"]].get("module") else {})} for p in self.pending}
        for p in self.pending:
            if p["key"] == "course":
                p["record"].update(self.index(titles, placed))
        for p in self.pending:
            record, printed, got = p["record"], p["printed"], placed[p["key"]]
            if record is not None:
                text = json.dumps(record, indent=1, ensure_ascii=False, default=str)
                (p["dir"] / RECORD).write_text(text + "\n", encoding="utf-8")
                printed = fingerprint(text)
            wants = set(links) if p["key"] == "course" else {*(record or {}).get("carries", ()), *([got["part_of"]] if got.get("part_of") else [])}
            linked = {k: links[k] for k in sorted(wants) if k in links}
            cap = {
                "v": 1,
                "slug": None,
                "item": f"blackboard:{self.cid}/{p['key']}",
                "title": titles[p["key"]],
                "body": p["body"],
                "fetched_at": self.fetched_at,
                "kind": p["kind"],
                "course": self.code,
                "course_name": self.course.get("name"),
                "published": p["published"],
                # The page's place, frontmatter and links are part of what it is: a moved position or a renamed link target re-renders it.
                "fingerprint": fingerprint(printed, got["place"], got["fields"], linked),
                **({"facts": p["facts"]} if p["facts"] else {}),
                "place": got["place"],
                "fields": got["fields"],
                **({"module": got["module"]} if got.get("module") else {}),
                **({"part_of": got["part_of"]} if got.get("part_of") else {}),
                **({"frozen": True} if got.get("frozen") else {}),
                **({"links": linked} if linked else {}),
            }
            (p["dir"] / CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        self.ledger.save()

    # ------------------------------------------------------------ layout

    def place(self, titles: dict[str, str]) -> dict[str, dict]:
        """Each capture's place under the job's dest (`<folder>/<stem>`, or None for the titles-only legacy layout) and its own
        frontmatter. A place is decided once, the first pull that sees the capture, and kept in the ledger: an instructor inserting an
        item renumbers no page that exists."""
        lay, o, led = self.layout, self.outline, self.ledger
        today = day(self.fetched_at)
        led.data["since"] = led.data.get("since") or today
        pages, modules = led.data.setdefault("pages", {}), led.data.setdefault("modules", {})
        keys = {p["key"] for p in self.pending}
        page_of = {o.anchor(p["node"]): p["key"] for p in self.pending if p["kind"] == "item" and p["node"] in o.rows}
        last_due: dict[str, str] = {}
        for p in self.pending:
            mid = o.module(p["node"]) if p["node"] in o.rows else None
            due = (self.grade_of.get(p["node"]) or {}).get("due") if p["kind"] == "item" else None
            if mid and due and due > last_due.get(mid, ""):
                last_due[mid] = due
        out = {}
        # Every place the ledger ever gave is taken, a dropped item's too: its page may still stand there, and a new item at the
        # same name would meet another item's page and never be written.
        used = {str(r.get("place")).casefold(): k for k, r in pages.items() if r.get("place")}
        for p in self.pending:
            key, node, kind = p["key"], p["node"], p["kind"]
            title = titles[key]
            mid = o.module(node) if node in o.rows else None
            fields = self.fields(p, title, mid)
            got = {"place": None, "fields": fields, "module": mid}
            if kind in ("file", "video") and node in o.rows and page_of.get(o.anchor(node)) in keys:
                got["part_of"] = page_of[o.anchor(node)]
            if mid and lay["backfill"] == "none" and mid in last_due:
                ends = datetime.fromisoformat(last_due[mid].replace("Z", "+00:00")) + FREEZE_GRACE
                got["frozen"] = ends < datetime.fromisoformat(self.fetched_at.replace("Z", "+00:00"))
            led.data.get("removed", {}).pop(key, None)  # back in the course; process clears `removed` on every listed item's page
            row = pages.get(key)
            if row is None:
                row = pages[key] = {"first_seen": today}
            if lay["layout"] != "legacy":
                if mid and lay["layout"] == "modules" and mid not in modules:
                    folder = self.module_folder(mid)
                    if folder.casefold() in {str(m.get("folder")).casefold() for m in modules.values()}:
                        # Two modules of one title (`prefix=none`, or one dropped and remade at its position): the id tells them apart.
                        folder = page_title(f"{folder} ({mid.strip('_')})")
                    modules[mid] = {"folder": folder, "released": today}
                if row.get("layout") != lay["layout"] or not row.get("place"):
                    place = self.planned(p, title, mid)
                    if used.get(place.casefold()) not in (None, key):
                        # Two captures cut to one name (a long title, `flat`): the key's tail tells them apart, as a shared title's does.
                        folder, _, stem = place.rpartition("/")
                        tail = f" ({key.rsplit('-', 1)[-1][-8:]})"
                        place = (folder + "/" if folder else "") + safe_title(stem[: TITLE_MAX - len(tail)].rstrip(" .…-") + tail)
                    row["place"], row["layout"] = place, lay["layout"]
                    used[place.casefold()] = key
                got["place"] = row["place"]
            out[key] = got
        return out

    def planned(self, p: dict, title: str, mid: str | None) -> str:
        """Where a capture first seen now goes: `NN Module/NN Item` (modules), `NN.NN Module — Item` (flat), a section folder for
        announcements and boards. The course code leaves the filename; the folder and the page's `title` carry it."""
        lay, o = self.layout, self.outline
        numbered = lay["prefix"] == "position"
        short = _short(title, self.code)
        if p["key"] == "course":
            return "00 Course overview" if numbered else "Course overview"
        if p["section"]:
            folder = lay[p["section"]]
            stem = short
            if p["section"] == "announcements" and numbered and p["record"] and day(p["record"].get("created")):
                stem = f"{day(p['record']['created'])} {short}"
            return safe_title(stem) if folder == ALONGSIDE else f"{folder}/{safe_title(stem)}"
        node = p["node"]
        if node not in o.rows:
            return safe_title(short)
        prefix = o.prefix(node)
        if not mid:
            return safe_title(f"{prefix} {short}" if numbered else short)
        if lay["layout"] == "flat":
            return page_title((f"{o.position(mid) + 1:02d}.{prefix} " if numbered else "") + f"{o.title(mid)} — {short}")
        return f"{self.module_folder(mid)}/{safe_title(f'{prefix} {short}' if numbered else short)}"

    def module_folder(self, mid: str) -> str:
        """The module's folder: the one the ledger says it was given, else `NN Title` by its position now."""
        made = (self.ledger.data.get("modules", {}).get(mid) or {}).get("folder")
        if made:
            return made
        title = self.outline.title(mid)
        return page_title(f"{self.outline.position(mid) + 1:02d} {title}" if self.layout["prefix"] == "position" else title)

    def fields(self, p: dict, title: str, mid: str | None) -> dict:
        """The page's own frontmatter beyond `type`, `resource`, `published` and `abstract`: what it is and where it sits.
        Grades, grade status and feedback stay in the body, dated by the pull, never fields."""
        o, node, record = self.outline, p["node"], p["record"] or {}
        kind = {"course": "overview", "announcement": "announcement", "discussion": "discussion", "file": "file", "video": "video"}.get(p["kind"])
        out: dict = {}
        if p["kind"] == "item":
            kind = page_kind(record.get("handler"), record.get("title") or title)
            out["bb_id"] = record.get("id")
        elif p["kind"] in ("announcement", "discussion"):
            out["bb_id"] = record.get("id")
        out = {"kind": kind, **out}
        if node in o.rows:
            out["outline_path"] = o.path(node)
            out["position"] = o.prefix(node)
            if mid and self.layout["layout"] != "modules":
                out["module"] = o.title(mid)
        g = record.get("grade") or (self.grade_of.get(node) if p["kind"] == "item" else None) or {}
        if g.get("due"):
            out["due"] = local_time(g["due"])
        if g.get("points"):
            out["points"] = f"{g['points']:g}"
        # `due` and `points` are always named: one the instructor took away is cleared on the page (`key=`), not left standing.
        return {**{k: v for k, v in out.items() if v not in (None, "")}, "due": out.get("due"), "points": out.get("points")}

    def index(self, titles: dict[str, str], placed: dict[str, dict]) -> dict:
        """What the course overview adds to its record: the outline with each row's page, due date and points; the modules with
        their folders; what was first seen in the last week; what left the course."""
        o, led = self.outline, self.ledger
        keys = {p["key"]: p for p in self.pending}
        page_of = {o.anchor(p["node"]): k for k, p in keys.items() if p["kind"] == "item" and p["node"] in o.rows}
        carried: dict[str, list[str]] = {}
        for k, p in keys.items():
            if p["kind"] in ("file", "video") and p["node"] in o.rows:
                carried.setdefault(o.anchor(p["node"]), []).append(k)
        # A course link in the outline that shares a board's title is that board: it names no id.
        named = Counter(str((p["record"] or {}).get("title") or "").casefold() for p in keys.values() if p["kind"] == "discussion")
        boards = {str(p["record"].get("title")).casefold(): k for k, p in keys.items()
                  if p["kind"] == "discussion" and named[str(p["record"].get("title") or "").casefold()] == 1}
        rows = []
        for cid in o.order:
            if o.anchor(cid) != cid and page_of.get(o.anchor(cid)):
                continue  # a folder's one item: the folder's row names its page
            c = o.rows[cid]
            g = self.grade_of.get(cid) or {}
            board = boards.get(str(c.get("title") or "").casefold()) if c.get("handler") == "resource/x-bb-courselink" else None
            if board:
                page_of.setdefault(cid, board)
                g = g or keys[board]["record"].get("grade") or {}
            rows.append({"depth": len(o.chain(cid)) - 1, "title": o.title(cid), "handler": c.get("handler"), "available": c.get("available"),
                         "url": c.get("url") if (c.get("url") or "").startswith("http") else None, "page": page_of.get(cid),
                         "carries": sorted(carried.get(cid, []), key=lambda k: titles[k]), "due": g.get("due"), "points": g.get("points")})
        today = datetime.fromisoformat(day(self.fetched_at)).date()  # a local day, as `first_seen` is
        since = led.data.get("since")
        added = sorted(((row.get("first_seen"), k) for k, row in led.data.get("pages", {}).items()
                        if k in keys and k != "course" and since and (row.get("first_seen") or "") > since
                        and (today - datetime.fromisoformat(row["first_seen"]).date()).days < ADDED_DAYS), reverse=True)
        modules = []
        for mid in o.modules():
            made = (led.data.get("modules") or {}).get(mid)
            if made:
                modules.append({"id": mid, "title": o.title(mid), "folder": made["folder"], "released": made.get("released"),
                                "order": module_order(o.title(mid)), "position": o.position(mid) + 1,
                                "kind": SHORT_HANDLER.get(o.rows[mid].get("handler"))})
        return {"outline": rows, "modules": modules, "added": [{"day": d, "page": k} for d, k in added],
                "removed": [{"day": r.get("day"), "title": r.get("title")} for r in sorted(led.data.get("removed", {}).values(), key=lambda r: r.get("day") or "")]}

    def removals(self, before: set[str], now: set[str]) -> None:
        """Items and boards an earlier pull made that this one did not list: after two whole pulls in a row without one, its
        capture is stamped `removed` with a new fingerprint, so the harvest posts it and process dates its page. A kind whose
        listing failed, a lesson that lists no children (the look of one not yet released), or an item still in the outline
        with nothing to render, judges nothing."""
        led = self.ledger
        missing, removed = led.data.setdefault("missing", {}), led.data.setdefault("removed", {})
        for key in now:
            missing.pop(key, None)
        failed = [str(e.get("what", "")) for e in _load(self.h, "errors.json", []) if isinstance(e, dict)]
        # Only an item and a board are judged, each where its own listing answered whole: a file or video leaves with its item
        # (or with `files=skip`), an announcement leaves at the end of its display window, a board with `discussions=skip`.
        # A listing that answered with nothing at all (a course closed to students, an outage that returns `[]`) judges nothing either:
        # an instructor emptying a whole course is rarer than a listing that came back blank.
        judged = tuple(kind for kind, listing in (("item-", ("contents",)), ("discussion-", ("discussions", "discussion messages")))
                       if not any(w.startswith(listing) for w in failed) and (kind != "discussion-" or self.discussions)
                       and any(k.startswith(kind) for k in now))
        for key in sorted(removed):
            # Dated once process says so (`DATED` in the capture): a stamp a failed edit never wrote is posted again.
            d = self.out / key
            if key not in now and (d / CAPTURE).is_file() and not (d / DATED).is_file():
                self.dirs.append(d)
        for key in sorted(before - now):
            if key in removed or not judged or not key.startswith(judged):
                continue
            if key.startswith("item-") and f"_{key.removeprefix('item-')}" in self.outline.rows:
                missing.pop(key, None)  # still in the outline, with nothing of its own to render: not gone
                continue
            d = self.out / key
            try:
                cap = json.loads((d / CAPTURE).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            mid = cap.get("module")
            if mid in self.outline.rows and not self.outline.kids.get(mid):
                continue
            missing[key] = missing.get(key, 0) + 1
            if missing[key] < 2:
                continue
            gone = day(self.fetched_at)
            cap["removed"] = gone
            cap["fingerprint"] = fingerprint(cap.get("fingerprint"), "removed", gone)
            (d / CAPTURE).write_text(json.dumps(cap, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            removed[key] = {"day": gone, "title": cap.get("title")}
            missing.pop(key, None)
            self.dirs.append(d)

    def run(self) -> list[Path]:
        h = self.h
        contents = _load(h, "contents.json", [])
        files = _load(h, "files.json", [])
        columns = _load(h, "gradebook-columns.json", [])
        grades = {g.get("columnId"): g for g in _load(h, "my-grades.json", [])}
        by_content = {c.get("contentId"): c for c in columns if c.get("contentId")}
        by_id = {c.get("id"): c for c in columns}
        items = {c["id"]: c for c in contents}
        self.outline = _Outline(contents)
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

        for c in contents:
            col = by_id.get(((c.get("raw") or {}).get("contentHandler") or {}).get("gradeColumnId")) or by_content.get(c["id"])
            if col:
                self.grade_of[c["id"]] = grade_facts(col)

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
                    self.write(key, "video", title, day(owner.get("modified")), body_file=src, extra=[words] if words else None, facts=where,
                               under=_folder(owner.get("path")), node=item_id)
                else:
                    if suffix in (".html", ".htm") and not html_text(src.read_text(encoding="utf-8", errors="replace")):
                        continue
                    alone = owner.get("handler") == "resource/x-bb-file"
                    title = f"{self.code} — {item_title(owner)}" + ("" if alone else f" — {src.name}")
                    self.write(key, "file", title, day(owner.get("modified")), body_file=src, facts=where, under=_folder(owner.get("path")), node=item_id)
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
                "carries": carried.get(item["id"], []),  # capture keys; the capture's `links` names their pages
            }
            record["title"] = item_title(item)
            self.write(f"item-{item['id'].strip('_')}", "item", f"{self.code} — {item_title(item)}", day(item.get("modified")), record=record,
                       under=_folder(item.get("path")), node=item["id"])

        for a in _load(h, "announcements.json", []):
            record = {"id": a.get("id"), "title": a.get("title"), "created": a.get("created"), "modified": a.get("modified"),
                      "shown_from": ((a.get("availability") or {}).get("duration") or {}).get("start"), "text": html_text(a.get("body"))}
            self.write(f"announcement-{str(a.get('id')).strip('_')}", "announcement", f"{self.code} announcement — {a.get('title')}",
                       day(a.get("modified") or a.get("created")), record=record, under=day(a.get("created")), section="announcements")

        for d in _load(h, "discussions.json", []) if self.discussions else []:
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
            self.write(f"discussion-{str(d.get('id')).strip('_')}", "discussion", f"{self.code} discussion — {d.get('title')}", day(last), record=record,
                       section="discussions")

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
        self.settle()
        return self.dirs


def _folder(path: str | None) -> str | None:
    """The folder above an item, by its path: what tells two same-titled items apart."""
    parts = [p for p in (path or "").split("/") if p and p.lower() != "ultradocumentbody"]
    return parts[-2] if len(parts) >= 2 else None


def _qualified(base: str, by: str) -> str:
    suffix = f" ({page_title(by)})"
    return safe_title(base[: max(1, TITLE_MAX - len(suffix))].rstrip() + suffix)


def split(harvest: Path, out: Path, fetched_at: str | None = None, *, course_id: str | None = None, discussions: bool = True,
          options: dict | None = None) -> list[Path]:
    """One capture dir per item under `out`, titles settled across the course; returns them in the order written, then any
    capture an earlier pull made that is now stamped `removed`.

    `course_id` stands in where `course.json` names none; with neither it raises `ValueError`. `discussions=False` makes no board's page.
    `options` are the job's (`layout_of`): where each page goes, and `backfill`; a word that is not one raises `ValueError`."""
    stamp = fetched_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _Split(harvest, out, stamp, course_id, discussions, options).run()


# ---------------------------------------------------------------- render


def _facts(rows: list[tuple[str, object]]) -> str:
    return "\n".join(f"- {k}: {one_line(v)}" for k, v in rows if v not in (None, "", []))


# The note format's bound on `abstract:`: one line of plain text, at most this many characters.
ABSTRACT_MAX = 600
SENTENCE = re.compile(r"(.+?[.?!])(?:\s|$)")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MARKS = re.compile(r"\*\*|__|`")
SLIDE = re.compile(r"^Slide \d+$")


def opening(text: str | None) -> str:
    """A text's first heading and first sentence, as plain words: `Reading: Read chapter 2 by Friday.`"""
    heading = None
    for raw in (text or "").splitlines():
        line = MARKS.sub("", raw)
        line = re.sub(r"^\\?[#>*\-\s]+", "", line).strip()
        if not line or raw.startswith("|") or SLIDE.match(line):
            continue
        if raw.lstrip().startswith("#") and heading is None:
            heading = line.rstrip(":")
            continue
        found = SENTENCE.match(line)
        sentence = found.group(1) if found else line
        return f"{heading}: {sentence}" if heading else sentence
    return heading or ""


def abstract(*parts) -> str:
    """The parts that are not empty, as one line no longer than `ABSTRACT_MAX`."""
    text = " ".join(" ".join(CONTROL.sub(" ", str(p)).split()) for p in parts if p not in (None, ""))
    # A link is never made here: the guard `html_text` puts on venue text stands, and a raw title gets it too.
    text = text.replace("[[", "[\\[").replace("]]", "]\\]")
    return text if len(text) <= ABSTRACT_MAX else text[: ABSTRACT_MAX - 1].rstrip() + "\u2026"


def _course_of(cap: dict) -> str:
    return course_title({"name": cap.get("course_name")}) if cap.get("course_name") else cap.get("course") or "the course"


def _due(g: dict) -> str | None:
    if not g:
        return None
    due = f"Due {when(g['due'])}." if g.get("due") else None
    pts = f"{g['points']:g} points." if g.get("points") else None
    return " ".join(x for x in (due, pts) if x) or None


def vtt_length(path: Path) -> str | None:
    """How long a caption track runs, by its last cue's end, as `12 min`; None where no cue says."""
    end = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        found = re.search(r"-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,]\d{3}", line)
        if found:
            end = int(found.group(1) or 0) * 3600 + int(found.group(2)) * 60 + int(found.group(3))
    if not end:
        return None
    if end < 60:
        return f"{end} s"
    h, m = divmod(round(end / 60), 60)
    return f"{h} h {m} min" if h else f"{m} min"


def _grade_rows(g: dict) -> list[tuple[str, object]]:
    if not g:
        return []
    score = None
    if g.get("score") is not None:
        score = f"{g['score']:g} of {g['points']:g}" if g.get("points") else f"{g['score']:g}"
    return [("Due", when(g.get("due"))), ("Points possible", f"{g['points']:g}" if g.get("points") else None),
            ("My grade", score), ("Grade status", g.get("status") if g.get("status") not in (None, "Graded") or score is None else None),
            ("Instructor feedback", html_text(g.get("feedback")).replace("\n", " ") if g.get("feedback") else None)]


def link_targets(cap: dict, given: dict | None = None) -> dict[str, str]:
    """Each page this capture links to, as the target a link names: `given`'s (process: the page's path, where `known[]` or the
    job's dest says it is), else its place, else its title."""
    out = {}
    for key, row in {**(cap.get("links") or {}), cap_key(cap): {"title": cap.get("title"), "place": cap.get("place")}}.items():
        out[key] = (given or {}).get(key) or row.get("place") or row.get("title") or key
    # A board's later parts and where its first part goes (`<key>#part-<n>`, `#base`, `#dir`), as process names them.
    own = f"{cap_key(cap)}#"
    out.update({k: v for k, v in (given or {}).items() if k.startswith(own) and v})
    return out


def cap_key(cap: dict) -> str:
    """The capture's own key: its directory's name, the tail of its `item`."""
    return str(cap.get("item") or "").rsplit("/", 1)[-1]


def wikilink(cap: dict, key: str, targets: dict[str, str], shown: str | None = None) -> str:
    title = shown or ((cap.get("links") or {}).get(key) or {}).get("title") or key
    target = targets.get(key) or title
    return f"[[{target}]]" if target == title else f"[[{target}|{title}]]"


def _render_item(cap: dict, r: dict, targets: dict[str, str]) -> list[dict]:
    kind = SHORT_HANDLER.get(r.get("handler"), r.get("handler"))
    head = _facts([("Course", cap.get("course_name")), ("Where", (r.get("path") or "").replace("/", " › ")), ("Kind", kind),
                   ("Syllabus", "yes" if r.get("syllabus") else None), ("Link", r.get("url")),
                   ("Posted", day(r.get("created"))), ("Last updated", day(r.get("modified"))), *_grade_rows(r.get("grade") or {})])
    parts = [f"# {one_line(r.get('title'))}", head]
    for heading, text in (("Description", r.get("description")), ("Instructions", r.get("instructions")), (None, r.get("text")), (None, r.get("wrapped"))):
        if text:
            parts.append((f"## {heading}\n\n" if heading else "") + (plain(text) if heading == "Description" else text))
    if r.get("carries"):
        parts.append("## Files and videos\n\n" + "\n".join(f"- {wikilink(cap, k, targets)}" for k in r["carries"] if k in targets))
    g = r.get("grade") or {}
    summary = abstract(f"{(kind or 'item').capitalize()} in {_course_of(cap)}, under {(r.get('path') or '').replace('/', ' › ')}." if r.get("path") else
                       f"{(kind or 'item').capitalize()} in {_course_of(cap)}.", _due(g),
                       opening(r.get("description") or r.get("instructions") or r.get("text") or r.get("wrapped")))
    return [{"title": cap["title"], "type": "document", "published": cap.get("published"), "abstract": summary, "body": "\n\n".join(parts) + "\n"}]


def _render_announcement(cap: dict, r: dict) -> list[dict]:
    head = _facts([("Course", cap.get("course_name")), ("Posted", day(r.get("created"))),
                   ("Last edited", day(r.get("modified")) if day(r.get("modified")) != day(r.get("created")) else None),
                   ("Shown from", day(r.get("shown_from")))])
    summary = abstract(f"Announcement in {_course_of(cap)}, posted {day(r.get('created')) or 'undated'}: {r.get('title')}.", opening(r.get("text")))
    return [{"title": cap["title"], "type": "note", "published": cap.get("published"), "abstract": summary,
             "body": f"# {one_line(r.get('title'))}\n\n{head}\n\n{r.get('text') or ''}\n"}]


def _render_discussion(cap: dict, r: dict, targets: dict[str, str]) -> list[dict]:
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
        block = f"{'#' * min(6, 3 + depth)} {label} {one_line(p['author'])}, {when(p.get('posted'))}\n\n{p.get('text') or ''}"
        return "\n\n".join([block] + [thread(c, depth + 1) for c in kids.get(p["id"], [])])

    head = _facts([("Course", cap.get("course_name")), ("Posts", len(posts)), *_grade_rows(r.get("grade") or {})])
    intro = f"# {one_line(r.get('title'))}\n\n{head}\n\n" + (f"## Prompt\n\n{r['prompt']}\n\n" if r.get("prompt") else "")
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
    said = abstract(f"Discussion board in {_course_of(cap)}: {r.get('title')}, {len(posts)} post{'' if len(posts) == 1 else 's'}.",
                    _due(r.get("grade") or {}), f"Prompt: {opening(r.get('prompt'))}" if r.get("prompt") else None)
    ck = cap_key(cap)
    own = targets.get(ck) or cap["title"]

    def part_at(m: int) -> str:
        """Where part `m` is: written (`#part-m`), else beside its first part's place, else its legacy title in `dest`."""
        if targets.get(f"{ck}#part-{m}"):
            return targets[f"{ck}#part-{m}"]
        if cap.get("place"):
            return f"{targets.get(ck + '#base') or own} (part {m})"
        name = page_title(f"{cap['title']} (part {m})")
        return f"{targets[ck + '#dir']}/{name}" if targets.get(ck + "#dir") else name

    for n, chunk in enumerate(chunks, 1):
        title = cap["title"] if n == 1 else page_title(f"{cap['title']} (part {n})")
        back = f"[[{own}]]" if own == cap["title"] else f"[[{own}|{cap['title']}]]"
        nxt, nxt_title = part_at(n + 1), page_title(cap["title"] + f" (part {n + 1})")
        lead = intro if n == 1 else f"# {one_line(r.get('title'))} (part {n} of {len(chunks)})\n\n{_facts([('Course', cap.get('course_name')), ('Continues', back)])}\n\n"
        tail = (f"\n\nContinued in [[{nxt}]]." if nxt == nxt_title else f"\n\nContinued in [[{nxt}|{nxt_title}]].") if n < len(chunks) else ""
        out.append({"title": title, "type": "note", "published": cap.get("published"),
                    "abstract": said if n == 1 else abstract(f"Part {n} of {len(chunks)} of {cap['title']}."),
                    "body": lead + ("## Posts\n\n" if chunk else "") + chunk.rstrip() + tail + "\n"})
    return out


def _render_course(cap: dict, r: dict, targets: dict[str, str]) -> list[dict]:
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
            fb = html_text(g.get("feedback")) if g.get("feedback") else ""
            pts = f"{g['points']:g}" if g.get("points") else ""
            lines.append(f"| {one_line(g['name'], cell=True)} | {when(g.get('due'))} | {pts} | {one_line(score, cell=True)} | {one_line(fb, cell=True)} |")
        parts.append("## Gradebook\n\n" + "\n".join(lines))
    if r.get("calendar"):
        parts.append("## Calendar\n\n" + "\n".join(f"- {when(e.get('start'))}: {one_line(e.get('title'))} ({one_line(e.get('type'))})" for e in r["calendar"]))
    outline = [o for o in r.get("outline") or [] if o.get("title")]
    if outline:
        lines = []
        for o in outline:
            pad = "  " * o.get("depth", 0)
            kind = SHORT_HANDLER.get(o.get("handler"), o.get("handler"))
            hidden = "" if o.get("available") in (None, "Yes", True) else f", {one_line(o['available'])}"
            name = wikilink(cap, o["page"], targets, one_line(o["title"])) if o.get("page") in targets else one_line(o.get("title"))
            due = f", due {when(o['due'])}" if o.get("due") else ""
            pts = f", {o['points']:g} points" if o.get("points") else ""
            lines.append(f"{pad}- {name} ({kind}{hidden}{due}{pts})" + (f" — {shown_url(o['url'])}" if o.get("url") else ""))
            lines += [f"{pad}  - {wikilink(cap, k, targets)}" for k in o.get("carries") or [] if k in targets]
        parts.insert(2, "## Outline\n\n" + "\n".join(lines))
    added = [a for a in r.get("added") or [] if a.get("page") in targets]
    if added:
        parts.insert(2, "## Added this week\n\n" + "\n".join(f"- {a['day']}: {wikilink(cap, a['page'], targets)}" for a in added))
    ext = [e for e in r.get("external") or [] if e.get("url")]
    if ext:
        parts.append("## Off-site links\n\n" + "\n".join(
            f"- {one_line(e.get('title') or e.get('item') or 'link')}{' (video)' if e.get('video') else ''}: {shown_url(e['url'])}" for e in ext))
    if r.get("removed"):
        parts.append("## Removed from the course\n\n" + "\n".join(f"- {one_line(x.get('title'))}: not listed since {x.get('day')}" for x in r["removed"]))
    graded = [g for g in rows if g.get("due")]
    summary = abstract(f"Course overview of {c.get('name') or _course_of(cap)}" + (f" ({c['courseId']})" if c.get("courseId") else "") + ":",
                       f"term {_term(term)}." if _term(term) else None,
                       f"{len(rows)} graded item{'' if len(rows) == 1 else 's'}." if rows else None,
                       f"{len(outline)} outline entr{'y' if len(outline) == 1 else 'ies'}." if outline else None,
                       f"Due dates run {day(min(g['due'] for g in graded))} to {day(max(g['due'] for g in graded))}." if graded else None)
    return [{"title": cap["title"], "type": "document", "published": cap.get("published"), "abstract": summary, "body": "\n\n".join(parts) + "\n"}]


def _term(term: dict) -> str | None:
    """A course's term as days, `2026-09-30 to 2026-12-15`; None where the course names no start."""
    start, end = day((term or {}).get("start")), day((term or {}).get("end"))
    return f"{start} to {end}" if start and end else f"from {start}" if start else None


def root_page(cap: dict, record: dict, current: bool, overview: str | None = None) -> dict:
    """The course's bundle root (`README.md` in the job's dest): the keys every page below inherits, and a line on what it is.
    `overview` is the link target of the course overview page; its title where none is given."""
    c = record.get("course") or {}
    title = course_title(c) if c.get("name") else _course_of(cap)
    term = _term(record.get("term") or {})
    span = record.get("term") or {}
    code = course_code(c) if c.get("name") or c.get("courseId") else cap.get("course")
    url = c.get("externalAccessUrl") or ""
    section = (c.get("courseId") or "").replace(" ", "")
    lead = re.match(r"[A-Za-z]{2,5}\s?-?\d{3,4}[A-Za-z]?-?", section)
    fields = {
        "root": "true", "current": "true" if current else "false", **({"term": term} if term else {}),
        "course": code, "course_title": title, "course_id": c.get("courseId"),
        "section": section[lead.end():] if lead and section[lead.end():] else None,
        "term_start": day(span.get("start")), "term_end": day(span.get("end")),
        "group": code, "group_type": "course", "channel": "blackboard",
        "source_host": urlsplit(url).hostname if url else None, "course_url": url or None,
    }
    fields = {k: v for k, v in fields.items() if v not in (None, "")}
    summary = abstract(f"{c.get('name') or title}" + (f" ({c['courseId']})" if c.get("courseId") else "") + ",",
                       f"term {term}," if term else None, "taken now" if current else "a past course",
                       "— the course's pages from Blackboard Learn.")
    target = overview or cap["title"]
    link = f"[[{target}]]" if target == cap["title"] else f"[[{target}|{cap['title']}]]"
    body = (f"# {title}\n\nThis course's pages from Blackboard Learn. The keys above are read by every page in this folder: "
            f"set `current: false` when the course is over. The outline, with every page in course order, the gradebook and the calendar: {link}.\n")
    return {"title": title, "fields": fields, "abstract": summary, "body": body}


def module_root(cap: dict, module: dict, overview: str | None = None) -> dict:
    """A module folder's bundle root (`README.md`): the module's keys, lent to every page in the folder over the course root's."""
    course = _course_of(cap)
    fields = {"root": "true", "module": module["title"], "module_order": module.get("order"), "module_position": module.get("position"),
              "module_kind": module.get("kind"), "released": module.get("released"), "module_id": module["id"]}
    fields = {k: str(v) for k, v in fields.items() if v not in (None, "")}
    target = overview or cap["title"]
    link = f"[[{target}]]" if target == cap["title"] else f"[[{target}|{cap['title']}]]"
    return {"title": f"{module['title']} ({cap.get('course') or course})", "fields": fields,
            "abstract": abstract(f"Module {module['title']} of {course}, from Blackboard Learn" +
                                 (f", first seen with its items {module['released']}." if module.get("released") else ".")),
            "body": f"# {one_line(module['title'])}\n\nThis module's pages in {one_line(course)}. The keys above are read by every page in "
                    f"this folder. The course outline, in order, with due dates: {link}.\n"}


def _render_file(cap: dict, path: Path) -> list[dict]:
    text, why = file_text(path)
    head = _facts([("Course", cap.get("course_name")), *_where(cap), ("File", path.name), ("Text", why)])
    title = cap["title"]
    f = cap.get("facts") or {}
    summary = abstract(f"{path.suffix.lstrip('.').upper() or 'File'} file {path.name} in {_course_of(cap)}" +
                       (f", carried by {f['owner']}." if f.get("owner") else "."), opening(text) or why)
    return [{"title": title, "type": "document", "published": cap.get("published"), "abstract": summary,
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
    length = vtt_length(words) if words else None
    name = cap["title"].split(" — ", 1)[-1].removesuffix(" (video)")
    summary = abstract(f"Video in {_course_of(cap)}: {name}" + (f", {length}." if length else "."),
                       opening(body) if body else why)
    return [{"title": cap["title"], "type": "video", "published": cap.get("published"), "abstract": summary,
             "body": f"# {cap['title'].split(' — ', 1)[-1]}\n\n{head}\n\n" + (f"## Transcript\n\n{body}\n" if body else ""), "problem": why}]


def render(directory: Path, links: dict[str, str] | None = None) -> list[dict]:
    """The page(s) one capture makes: `title`, `type`, `published`, `abstract`, `body`, and `problem` where text could not be had.

    `links` maps a capture key to the target a link to its page names (process: the page's path); the capture's place, else its
    title, stands in for a key it does not name."""
    cap = json.loads((directory / CAPTURE).read_text(encoding="utf-8"))
    body = directory / cap["body"]
    kind = cap.get("kind")
    if kind == "file":
        return _render_file(cap, body)
    if kind == "video":
        return _render_video(cap, body, directory)
    record = json.loads(body.read_text(encoding="utf-8"))
    targets = link_targets(cap, links)
    if kind == "announcement":
        return _render_announcement(cap, record)
    return {"item": _render_item, "discussion": _render_discussion, "course": _render_course}[kind](cap, record, targets)


# ---------------------------------------------------------------- cli


def _frontmatter(page: dict, cap: dict) -> str:
    # No `resource`: that is a job's page identity, which `process.py` sets; a dropped note belongs to no job.
    rows = {"type": page["type"], **({"title": page["title"]} if cap.get("place") else {}), "published": page.get("published"),
            "course": cap.get("course"), "abstract": page.get("abstract"), **(cap.get("fields") or {})}
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
    for p in (sub.choices["split"], sub.choices["notes"]):
        p.add_argument("--layout", choices=CHOICES["layout"], default="legacy", help="where each note goes, as a job's options.layout")
    for p in sub.choices.values():
        p.add_argument("--tz", help="the zone due dates and post times read in, an IANA name (default UTC)")
    args = ap.parse_args(argv)
    set_zone(args.tz)
    if args.cmd == "split":
        if not (args.harvest / "course.json").is_file():
            print(f"refused: {args.harvest} holds no course.json — not a `bb.py harvest` output", file=sys.stderr)
            return 2
        try:
            dirs = split(args.harvest, args.out, options={"layout": args.layout})
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
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
    try:
        dirs = split(args.harvest, items, options={"layout": args.layout})
    except ValueError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    for d in dirs:
        cap = json.loads((d / CAPTURE).read_text(encoding="utf-8"))
        for n, page in enumerate(render(d), 1):
            place = f"{cap['place']} (part {n})" if cap.get("place") and n > 1 else cap.get("place") or page["title"]
            target = args.out / f"{place}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(_frontmatter(page, cap) + page["body"], encoding="utf-8")
            written += 1
            if page.get("problem"):
                problems.append(f"{page['title']}: {page['problem']}")
    print(f"{written} notes -> {args.out}")
    for line in problems:
        print(f"  no text: {line}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
