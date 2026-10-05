"""The two YouTube enrich units, the harness tier: each installed and enabled
through the REAL CLI beside `channel-youtube`, a capture carried through the
rail by the runner — harvest, then the enrich ticket the harvest's landing
mints, then (local unit) the enrich session and process — and the page that
lands carries the notes.

Not covered here: the gemini unit's enrich stage itself, because the jail
reaches only the real Gemini host and nothing here may; its script is tested
against a local server in the unit's own tests. And the local unit's frame
cut, which needs a real video from `yt-dlp`: its session plan seals notes
written without one.
"""

from __future__ import annotations

import json
import re
import shutil

from harness import YT_FIXTURES, bound_credential, claimed, declared_job, enabled, pending, shown, staged, unit_tests

YT = unit_tests("channel-youtube", "test_youtube")

GEMINI_UNIT = "channel-youtube-watch-gemini"
LOCAL_UNIT = "channel-youtube-watch-local"
NOTE = "ops/skills/channel-youtube/scripts/youtube_note.py"
FRAMES = f"ops/skills/{LOCAL_UNIT}/scripts/watch_frames.py"


def _held(item: str) -> None:
    """What `yt-dlp` answers for `item`: the metadata and caption fixtures."""
    video = YT_FIXTURES / item.rsplit("v=", 1)[1]
    video.mkdir(parents=True, exist_ok=True)
    meta = {**YT["META"], "webpage_url": item}
    (video / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    shutil.copy(YT["FIXTURES"] / "dQw4fixture.en.vtt", video / f"{meta['id']}.en.vtt")


def _harvested(ops, env, wiki, unit, target, slug, *extra, credential=None):
    """A `channel-youtube` job that names `unit` as its enrich unit, harvested
    by the runner; returns the job, the capture dir and the enrich ticket the
    harvest's landing minted."""
    _held(target)
    enabled(ops, env, wiki, unit)
    job = declared_job(ops, env, wiki, YT["UNIT"], target, f"enrich.skill={unit}", *extra, slug=slug)
    if credential:
        bound_credential(ops, env, wiki, slug, credential)
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, "")
    landed = shown(ops, env, wiki, ticket_id)
    assert landed["state"] == "done", (landed["reason"], session.log[-3000:])
    (enrich_id,) = pending(ops, env, wiki, job.slug, "enrich").values()
    return job, cap, enrich_id


def test_the_harvest_landing_mints_the_gemini_enrich_ticket_with_the_jobs_options(ops, env, wiki):
    job, _cap, enrich_id = _harvested(
        ops, env, wiki, GEMINI_UNIT, "https://www.youtube.com/watch?v=gemAAAAAAAA", "harness-yt-gemini",
        "enrich.options.question=What is shown on screen?", "enrich.options.model=gemini-harness",
        credential="gemini-key",
    )
    ticket = shown(ops, env, wiki, enrich_id)
    assert ticket["queue"] == "enrich" and ticket["unit"] == GEMINI_UNIT


def test_the_local_unit_carries_a_capture_through_enrich_to_a_page_with_watch_notes(ops, env, wiki):
    target = "https://www.youtube.com/watch?v=locAAAAAAAA"
    job, cap, enrich_id = _harvested(ops, env, wiki, LOCAL_UNIT, target, "harness-yt-local")
    assert shown(ops, env, wiki, enrich_id)["unit"] == LOCAL_UNIT

    # SKILL.md's steps 3 to 5, with the notes the session would have written.
    session = staged(ops, env, wiki, enrich_id, f"""\
printf -- '- [00:07] A test pattern counts up.\\n' > "$CAP/enrich-notes.tmp"
mkdir -p "$CAP/enrich" && mv "$CAP/enrich-notes.tmp" "$CAP/enrich/watch.md"
step seal "$OPS" run {FRAMES} seal --capture-dir "$CAP"
step update "$OPS" --json pipeline tickets update "$TICKET" stage=enrich status=ok produced=1
""")
    for name in ("seal", "update"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    assert sorted(p.name for p in (cap / "enrich").iterdir()) == ["watch.json", "watch.md"]

    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    session = staged(ops, env, wiki, process_id, f"""\
rm -f "$CAP/page.md" "$CAP/written.json"
step note "$OPS" run {NOTE} . --capture-dir "$CAP" --dest {job.dest} --ticket "$TICKET"
step update "$OPS" --json pipeline tickets update "$TICKET" stage=process status=ok written_from=written.json
""")
    for name in ("note", "update"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    out = json.loads(session.step("note").stdout)
    assert out["watch_notes"] is True
    page = (wiki / out["written"][0]).read_text(encoding="utf-8")
    assert re.findall(r"^## .*$", page, re.M) == ["## Description", "## Watch notes", "## Transcript"]
    section = page.split("## Watch notes\n\n", 1)[1].split("\n## ", 1)[0]
    assert section.startswith("*A model read sampled frames and the captions.")
    assert "> - [00:07] A test pattern counts up." in section
    assert len(re.findall(r"^---$", page, re.M)) == 2, "only the page verb's own frontmatter fences"
