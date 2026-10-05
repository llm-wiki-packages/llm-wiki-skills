"""The two YouTube enrich units, the harness tier: each installed and enabled
through the REAL CLI beside `channel-youtube`, a capture carried through the
rail — harvest, then enrich, then process — and the page that lands carries
the notes.

What this cannot do: a model session reading frames (the local unit's
`SKILL.md` steps 3 is the session's, played here by writing the file), and a
jailed run spending a bound key against the live API. Both are named in the
units' own docs as unverified.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys

import pytest

from harness import advanced, bound_credential, declared_job, enabled, landed, live_ticket, rooted, run, unit_tests

YT = unit_tests("channel-youtube", "test_youtube")
GEM = unit_tests("channel-youtube-watch-gemini", "test_watch_gemini")
gemini = GEM["gemini"]  # a local server that speaks the Interactions API's shape

GEMINI_UNIT = "channel-youtube-watch-gemini"
LOCAL_UNIT = "channel-youtube-watch-local"
KEY = "harness-gemini-key"
NOTES = GEM["ANSWER"]


def _needs_run_verb(ops, env, wiki):
    if run(ops, rooted(env, wiki), "pipeline", "tickets", "run", "--help").returncode != 0:
        pytest.skip("`pipeline tickets run` (spawn=self) is plugins PR 2 (#2486)")


def _enrich_job(ops, env, wiki, unit, target, slug, *extra, credential=None):
    """A `channel-youtube` job that names `unit` as its enrich unit, its
    harvest done: the capture is filled, `capture.json` written, and the
    harvest ticket landed — which must mint the ENRICH ticket, opened and
    returned with the capture directory it shares with process."""
    _needs_run_verb(ops, env, wiki)
    enabled(ops, env, wiki, unit)
    job = declared_job(ops, env, wiki, YT["UNIT"], target, f"enrich.skill={unit}", *extra, slug=slug)
    if credential:  # a unit that needs one cannot be claimed past the harvest without it
        bound_credential(ops, env, wiki, slug, credential, KEY)
    harvest_id, cap = live_ticket(ops, env, wiki, job)
    YT["_fill"](cap)
    r = run(ops, rooted(env, wiki), "run", "ops/skills/channel-youtube/scripts/youtube_note.py", ".",
            "--capture-dir", str(cap.relative_to(wiki)), "--record", "--ticket", harvest_id, cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "update", harvest_id, "stage=harvest", "status=ok")
    assert r.returncode == 0, r.stdout + r.stderr
    enrich_id, enrich_cap = advanced(ops, env, wiki, harvest_id)
    assert enrich_cap == cap
    opened = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "open", enrich_id).data["ticket"]
    assert opened["stage"] == "enrich", f"harvest close minted a {opened['stage']} ticket, not the enrich one"
    return job, enrich_id, cap, opened


def _process(ops, env, wiki, tmp_path, job, enrich_id, cap):
    """Land the enrich ticket, then run channel-youtube's own process step on
    the process ticket it mints: the page is what the whole rail made."""
    process_id, process_cap = advanced(ops, env, wiki, enrich_id)
    assert process_cap == cap
    r = run(ops, rooted(env, wiki), "run", "ops/skills/channel-youtube/scripts/youtube_note.py", ".",
            "--capture-dir", str(cap.relative_to(wiki)), "--dest", job.dest, "--ticket", process_id,
            "--format-transcript", str(YT["_stub_formatter"](tmp_path)), cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout)
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "update", process_id, "stage=process",
            "status=ok", "written_from=written.json")
    assert r.returncode == 0, r.stdout + r.stderr
    landed(ops, env, wiki, process_id)
    return out, (wiki / out["written"][0]).read_text(encoding="utf-8")


def _section(page: str) -> str:
    return page.split("## Watch notes\n\n", 1)[1].split("\n## ", 1)[0]


def test_the_gemini_unit_carries_a_capture_through_enrich_to_a_page_with_watch_notes(ops, env, wiki, gemini, tmp_path):
    target = "https://www.youtube.com/watch?v=gemAAAAAAAA"
    job, enrich_id, cap, opened = _enrich_job(
        ops, env, wiki, GEMINI_UNIT, target, "harness-yt-gemini",
        "enrich.options.question=What is shown on screen?", "enrich.options.model=gemini-harness",
        credential="gemini-key",
    )
    # What the unit reads off its own ticket, asked of the real CLI.
    assert opened["enrich"]["options"] == {"question": "What is shown on screen?", "model": "gemini-harness"}
    assert opened["credential"] == "gemini-key" and opened.get("credential_route") is None

    r = run(ops, rooted(env, wiki), "run", f"ops/skills/{GEMINI_UNIT}/scripts/watch_gemini.py", f"ticket={enrich_id}",
            "--api-base", gemini.base, cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    (request,) = gemini.seen
    assert request["key"] == KEY, "the bound key rode the x-goog-api-key header"
    assert request["body"]["model"] == "gemini-harness"
    assert request["body"]["input"][0]["uri"] == target, "the job's own target is the video that is watched"
    assert request["body"]["input"][1]["text"] == "What is shown on screen?"
    assert sorted(p.name for p in (cap / "enrich").iterdir()) == ["watch.json", "watch.md"]

    out, page = _process(ops, env, wiki, tmp_path, job, enrich_id, cap)
    assert out["watch_notes"] is True
    assert [h for h in re.findall(r"^## .*$", page, re.M)] == ["## Description", "## Watch notes", "## Transcript"]
    section = _section(page)
    assert section.startswith("*Google's Gemini watched the video (gemini-harness).")
    assert "> - [00:10] Progressive overload is defined." in section
    assert len(re.findall(r"^---$", page, re.M)) == 2, "only the page verb's own frontmatter fences"


def test_a_failed_enrich_leaves_no_files_and_routes_the_capture_nowhere_yet(ops, env, wiki, gemini, tmp_path):
    job, enrich_id, cap, _ = _enrich_job(
        ops, env, wiki, GEMINI_UNIT, "https://www.youtube.com/watch?v=gemBBBBBBBB", "harness-yt-gemini-fail",
        credential="gemini-key-fail")
    gemini.answers[:] = [(401, {"error": {"message": f"key {KEY} rejected"}})]
    r = run(ops, rooted(env, wiki), "run", f"ops/skills/{GEMINI_UNIT}/scripts/watch_gemini.py", f"ticket={enrich_id}",
            "--api-base", gemini.base, cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (cap / "enrich").exists() and KEY not in r.stdout + r.stderr
    closed = landed(ops, env, wiki, enrich_id)["closed"][0]
    assert closed["state"] != "done" and closed["enqueued"] == [], f"a failed enrich must not route the capture on: {closed}"


def _stub_ytdlp(tmp_path, clip):
    """A `yt-dlp` that hands over `clip` where the unit's `-o` template says."""
    bindir = tmp_path / "yt-dlp-bin"
    bindir.mkdir()
    stub = bindir / "yt-dlp"
    stub.write_text(
        f"#!{sys.executable}\nimport shutil, sys\n"
        "out = sys.argv[sys.argv.index('-o') + 1].replace('%(ext)s', 'mp4')\n"
        f"shutil.copy({str(clip)!r}, out)\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return bindir


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe are not on PATH")
def test_the_local_unit_carries_a_capture_through_enrich_to_a_page_with_watch_notes(ops, env, wiki, tmp_path):
    job, enrich_id, cap, opened = _enrich_job(
        ops, env, wiki, LOCAL_UNIT, "https://www.youtube.com/watch?v=locAAAAAAAA", "harness-yt-local",
        "enrich.options.max_frames=5",
    )
    assert str(opened["enrich"]["options"]["max_frames"]) == "5"
    clip = tmp_path / "clip.mp4"
    made = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=20:size=640x360:rate=10", "-pix_fmt", "yuv420p", str(clip)],
        capture_output=True, text=True,
    )
    assert made.returncode == 0, made.stderr
    local_env = {**rooted(env, wiki), "PATH": f"{_stub_ytdlp(tmp_path, clip)}{os.pathsep}{env['PATH']}"}
    script = f"ops/skills/{LOCAL_UNIT}/scripts/watch_frames.py"
    rel = str(cap.relative_to(wiki))

    r = run(ops, local_env, "run", script, "frames", "--item", YT["ITEM"], "--capture-dir", rel, "--max-frames", "5", cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    frames = json.loads(r.stdout)["frames"]
    assert len(frames) == 4 and all((cap / "enrich" / "frames" / os.path.basename(f["path"])).is_file() for f in frames)

    r = run(ops, local_env, "run", script, "transcript", "--capture-dir", rel, cwd=wiki)
    assert r.returncode == 0 and "Progressive overload means doing" in r.stdout, r.stdout + r.stderr

    # The session's own step: look, then write the notes.
    (cap / "enrich" / "watch.md").write_text("- [00:07] A test pattern counts up.\n", encoding="utf-8")
    r = run(ops, local_env, "run", script, "seal", "--capture-dir", rel, cwd=wiki)
    assert r.returncode == 0, r.stdout + r.stderr
    assert sorted(p.name for p in (cap / "enrich").iterdir()) == ["watch.json", "watch.md"]
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "update", enrich_id, "stage=enrich", "status=ok", "produced=1")
    assert r.returncode == 0, r.stdout + r.stderr

    out, page = _process(ops, env, wiki, tmp_path, job, enrich_id, cap)
    assert out["watch_notes"] is True
    section = _section(page)
    assert section.startswith("*A model read sampled frames and the captions.")
    assert "> - [00:07] A test pattern counts up." in section
