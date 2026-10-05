"""channel-youtube, the harness tier: the unit installed and enabled through the REAL
CLI, each stage started by the runner in the jail it composes — the harvest
its own `script`, `capture_video.py`, over the `yt-dlp` stand-in the
harness's PATH leads with (fixtures; no network), and the process a session
the harness profile's fake agent stands in for. Its helpers and constants are
the unit's own tests' — `skills/channel-youtube/tests/test_youtube.py`, which
ships with the unit — so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import json
import re
import shutil

import pytest

from harness import YT_FIXTURES, claimed, declared_job, pending, shown, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-youtube", "test_youtube"))

NOTE = "ops/skills/channel-youtube/scripts/youtube_note.py"


def held(item: str, meta: dict) -> None:
    """What `yt-dlp` answers for `item`: its metadata and its caption track."""
    video = YT_FIXTURES / item.rsplit("v=", 1)[1]
    video.mkdir(parents=True, exist_ok=True)
    (video / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    shutil.copy(FIXTURES / "dQw4fixture.en.vtt", video / f"{meta['id']}.en.vtt")


def harvested(ops, env, wiki, job):
    """The harvest stage, the runner's own: `capture_video.py` in its jail."""
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, "")  # a script stage: no session, nothing for the fake agent to type
    landed = shown(ops, env, wiki, ticket_id)
    assert landed["state"] == "done", (landed["reason"], session.log[-3000:])
    return cap


def processed(ops, env, wiki, job, cap):
    """The process stage, a session in its jail: SKILL.md's steps 1, 3 and 4."""
    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    session = staged(ops, env, wiki, process_id, f"""\
rm -f "$CAP/page.md" "$CAP/written.json"
step note "$OPS" run {NOTE} . --capture-dir "$CAP" --dest {job.dest} --ticket "$TICKET"
step update "$OPS" --json pipeline tickets update "$TICKET" stage=process status=ok written_from=written.json
""")
    for name in ("note", "update"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    return json.loads(session.step("note").stdout)


def test_a_harvested_video_becomes_the_staged_page(ops, env, wiki):
    """The whole point of the rework. The harvest's own script over what yt-dlp
    leaves → the capture record → this unit's own process step, through the
    REAL `page create` and the plugin's real formatter → one staged page under
    the job's `dest`, carrying the venue-specific body and the venue's own facts."""
    held(ITEM, META)
    job = declared_job(ops, env, wiki, UNIT, JOB_TARGET)
    cap = harvested(ops, env, wiki, job)
    record = json.loads((cap / "capture.json").read_text())
    assert record["slug"] == job.slug and record["item"] == ITEM and "frontmatter" not in record

    out = processed(ops, env, wiki, job, cap)
    assert out["has_transcript"] is True and out["chapters"] == 2

    page = wiki / out["written"][0]
    text = page.read_text(encoding="utf-8")
    assert page.is_relative_to(wiki / job.dest), page

    # ONE frontmatter block — the page verb's — and the body after it is ours, verbatim.
    assert text.startswith("---\n")
    _, front, body = text.split("---\n", 2)
    assert "status: draft" in front and ITEM in front and "Progressive Overload, Explained" in front
    # the facts the unit knows are ON THE PAGE, not re-guessed from the body
    assert "type: video" in front and "published: '2026-06-18'" in front and "extracted: 'true'" in front
    assert body.strip() == (cap / "page.md").read_text(encoding="utf-8").strip()
    # The description is a blockquote, so the page verb's two fences are all there are.
    assert len(re.findall(r"^---$", text, re.M)) == 2, "the two fences of the one frontmatter block"
    assert body.lstrip().startswith("# Progressive Overload, Explained\n")

    # the venue-specific body survived
    assert "![thumbnail](https://i.ytimg.com/vi/dQw4fixture/maxresdefault.jpg)" in body
    assert 'src="https://www.youtube.com/embed/dQw4fixture"' in body
    assert "- **Published**: 2026-06-18" in body and "- **Views**: 517273 · **Likes**: 16124" in body
    assert "- `1:30` How to progress" in body and "#strength" not in body
    # the real formatter: chapter-headed, de-duplicated, no cue markup, no sound tags
    assert re.search(r"^#+ \[00:00\] What overload is$", body, re.M) and re.search(r"^#+ \[01:30\] How to progress$", body, re.M)
    assert body.count("Progressive overload means doing") == 1
    assert "<c>" not in body and "[Music]" not in body
    assert "[!summary]" not in body


# Rule 1 — the page's FILE is named from `capture.json`'s title, and the host
# refuses a title its filename rule cannot hold (`page/note.py`: ILLEGAL, and
# what `filename_for` refuses).
@pytest.mark.parametrize("leaf, title, safe", [
    ("hostile--5e2e0002", 'Lesson 3: Pricing? A/B "testing"', "Lesson 3 - Pricing A-B ’testing’"),
    ("hostile--5e2e0003", ".hidden: what is <X> | Y?\n---\n# Forged", "hidden - what is (X) - Y --- # Forged"),
    ("hostile--5e2e0004", "漢" * 100, None),
])
def test_a_title_no_filename_can_hold_still_lands_as_a_page(ops, env, wiki, leaf, title, safe):
    """Through the REAL `page create`, which names the page's file from the
    title and refuses `:` `?` `/` `"` or a leading dot outright."""
    # A wiki holds ONE job per target url — every hostile case gets its own
    # target, not just its own slug.
    item = f"https://www.youtube.com/watch?v={leaf[-8:]}xyz"
    held(item, {**META, "title": title, "webpage_url": item})
    job = declared_job(ops, env, wiki, UNIT, item, slug=f"harness-yt-{leaf}")
    cap = harvested(ops, env, wiki, job)
    record = json.loads((cap / "capture.json").read_text())

    # The refusal this pins is `page create`'s own, not an assertion of ours.
    out = processed(ops, env, wiki, job, cap)
    if safe:
        assert record["title"] == safe
    page = wiki / out["written"][0]
    assert page.is_file() and page.name == f"{record['title']}.md"
    text = page.read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    folded = " ".join(title.split())
    assert body.lstrip().startswith(f"# {folded.replace('<', '&lt;')}\n"), "the TRUE title is the H1"
    assert "source_title: " in front and folded[:20] in front
    assert len(re.findall(r"^---$", text, re.M)) == 2 and "\n# Forged" not in text
