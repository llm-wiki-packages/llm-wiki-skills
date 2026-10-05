"""watch_frames.py: the pure parts against inline fixtures, and `frames` through
a stub `yt-dlp` that hands over a clip ffmpeg synthesized — so nothing here
touches a network, and the cases that need ffmpeg skip, saying so, without it."""

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

UNIT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = UNIT_DIR / "scripts" / "watch_frames.py"
URL = "https://www.youtube.com/watch?v=dQw4fixture"
LEAF = "_raw/job/leaf"

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe are not on PATH")


def _load():
    spec = importlib.util.spec_from_file_location("watch_frames", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


# ------------------------------------------------------------------- pure logic


def test_the_clock_reads_like_a_timestamp(mod):
    assert [mod.clock(s) for s in (0, 59.6, 61, 3599, 3600, 3725)] == ["00:00", "01:00", "01:01", "59:59", "1:00:00", "1:02:05"]


@pytest.mark.parametrize("duration, cap, count", [(5, 24, 4), (60, 24, 4), (300, 24, 20), (3600, 24, 24), (3600, 60, 60), (1, 2, 2)])
def test_the_plan_is_a_few_frames_for_a_short_clip_and_never_more_than_the_cap(mod, duration, cap, count):
    moments = mod.plan(duration, cap)
    assert len(moments) == count
    assert moments == sorted(moments) and 0 < moments[0] and moments[-1] < duration


ROLLING = """WEBVTT
Kind: captions

00:00:01.000 --> 00:00:03.000 align:start position:0%
Progressive overload means<00:00:02.000><c> doing</c><c> more</c>

00:00:03.000 --> 00:00:03.010 align:start position:0%
Progressive overload means doing more

00:00:03.010 --> 00:00:05.000 align:start position:0%
Progressive overload means doing more
over the weeks

00:00:05.000 --> 00:00:06.000
[Music]

00:00:41.000 --> 00:00:43.000
Second bucket starts here
"""


def test_rolling_captions_are_deduplicated_bucketed_and_stripped_of_sound_tags(mod):
    got = mod.transcript_of(ROLLING).split("\n")
    assert got == ["[00:00] Progressive overload means doing more over the weeks", "[00:30] Second bucket starts here"]


def test_an_srt_reads_the_same_way(mod):
    srt = "1\n00:00:01,000 --> 00:00:02,000\nHello there\n\n2\n01:00:00,500 --> 01:00:02,000\nAn hour in\n"
    assert mod.transcript_of(srt) == "[00:00] Hello there\n[1:00:00] An hour in"


def test_captions_are_found_under_captions_before_beside_the_metadata(mod, tmp_path):
    (tmp_path / "captions").mkdir()
    (tmp_path / "x.en.vtt").write_text(ROLLING)
    (tmp_path / "captions" / "a.en.vtt").write_text(ROLLING)
    assert mod.find_captions(tmp_path) == tmp_path / "captions" / "a.en.vtt"
    assert mod.find_captions(tmp_path / "captions" / "nowhere") is None


@pytest.mark.parametrize("url, ok", [
    (URL, True), ("https://youtu.be/dQw4fixture", True), ("https://www.youtube.com/shorts/abc", True),
    ("https://vimeo.com/1", False), ("file:///etc/passwd", False), ("https://evil.example/watch?v=x", False), (None, False),
])
def test_only_youtube_urls_are_fetched(mod, url, ok):
    assert mod.is_youtube(url) is ok


# ----------------------------------------------------------------- the commands


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    """The wiki root a `run` starts at; the capture dir is relative to it."""
    (tmp_path / LEAF).mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("clip") / "clip.mp4"
    cp = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=20:size=640x360:rate=10", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True,
    )
    assert cp.returncode == 0, cp.stderr
    return path


@pytest.fixture
def ytdlp(tmp_path, monkeypatch):
    """A `yt-dlp` first on PATH. `ytdlp.clip` is copied to the `-o` template;
    `ytdlp.fail` is a stderr to die with instead. Every argv lands in `ytdlp.calls()`."""
    bindir, log = tmp_path / "stub-bin", tmp_path / "ytdlp-calls.jsonl"
    bindir.mkdir()
    config = tmp_path / "ytdlp.json"
    config.write_text("{}")
    stub = bindir / "yt-dlp"
    stub.write_text(
        f"#!{sys.executable}\nimport json, shutil, sys\n"
        f"open({str(log)!r}, 'a').write(json.dumps(sys.argv[1:]) + '\\n')\n"
        f"cfg = json.load(open({str(config)!r}))\n"
        "if cfg.get('fail'):\n"
        "    sys.stderr.write(cfg['fail']); sys.exit(1)\n"
        "out = sys.argv[sys.argv.index('-o') + 1].replace('%(ext)s', 'mp4')\n"
        "shutil.copy(cfg['clip'], out)\n"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")

    class Stub:
        def set(self, **kw):
            config.write_text(json.dumps(kw))

        def calls(self):
            return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    return Stub()


def frames(mod, *extra, item=URL):
    return mod.main(["frames", "--item", item, "--capture-dir", LEAF, *extra])


@needs_ffmpeg
def test_frames_cuts_stills_deletes_the_video_and_names_each_by_path_and_clock(mod, wiki, clip, ytdlp, capsys):
    ytdlp.set(clip=str(clip))
    (wiki / LEAF / "enrich").mkdir()
    (wiki / LEAF / "enrich" / "stale.txt").write_text("old")
    assert frames(mod, "--max-frames", "6") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["duration"] == 20.0
    assert [f["clock"] for f in out["frames"]] == [mod.clock(m) for m in mod.plan(20.0, 6)] and len(out["frames"]) == 4
    for f in out["frames"]:
        assert Path(f["path"]).is_absolute() and Path(f["path"]).read_bytes()[:2] == b"\xff\xd8"
    enrich = wiki / LEAF / "enrich"
    assert sorted(p.name for p in enrich.iterdir()) == ["frames", "frames.json"], "no stale file, and the downloaded video is gone"
    (call,) = ytdlp.calls()
    assert call[:2] == ["--no-playlist", "--no-progress"] and call[-2:] == ["--", URL]


@needs_ffmpeg
def test_the_frames_are_scaled_to_the_width(mod, wiki, clip, ytdlp, capsys):
    ytdlp.set(clip=str(clip))
    frames(mod)
    first = json.loads(capsys.readouterr().out)["frames"][0]["path"]
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width", "-of", "csv=p=0", first], capture_output=True, text=True)
    assert cp.stdout.strip() == str(mod.FRAME_WIDTH)


def test_a_private_video_is_a_lasting_fact_and_leaves_nothing(mod, wiki, ytdlp, capsys):
    ytdlp.set(fail="ERROR: [youtube] abc: Private video. Sign in if you've been granted access\n")
    assert frames(mod) == 3
    assert json.loads(capsys.readouterr().out)["lasting"] is True
    assert not (wiki / LEAF / "enrich").exists()


def test_any_other_download_failure_is_a_failure_and_leaves_nothing(mod, wiki, ytdlp):
    ytdlp.set(fail="ERROR: unable to download: HTTP Error 503\n")
    with pytest.raises(SystemExit) as exc:
        frames(mod)
    assert "yt-dlp failed" in str(exc.value) and "503" in str(exc.value)
    assert not (wiki / LEAF / "enrich").exists()


def test_a_url_that_is_not_youtube_runs_nothing(mod, wiki, ytdlp, capsys):
    assert frames(mod, item="https://vimeo.com/1") == 3
    assert json.loads(capsys.readouterr().out)["reason"].startswith("not_youtube") and ytdlp.calls() == []


def test_transcript_prints_the_buckets_and_writes_nothing(mod, wiki, capsys):
    (wiki / LEAF / "captions").mkdir()
    (wiki / LEAF / "captions" / "v.en.vtt").write_text(ROLLING)
    before = sorted(wiki.rglob("*"))
    assert mod.main(["transcript", "--capture-dir", LEAF]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("[00:00] Progressive overload means doing more over the weeks")
    assert sorted(wiki.rglob("*")) == before


def test_a_video_without_captions_says_so_and_writes_nothing(mod, wiki, capsys):
    assert mod.main(["transcript", "--capture-dir", LEAF]) == 0
    assert "no captions" in capsys.readouterr().out and not (wiki / LEAF / "enrich").exists()


def _notes(wiki, text):
    enrich = wiki / LEAF / "enrich"
    (enrich / "frames").mkdir(parents=True)
    (enrich / "frames" / "001.jpg").write_bytes(b"\xff\xd8")
    (enrich / "frames.json").write_text(json.dumps([{"file": "001.jpg"}, {"file": "002.jpg"}]))
    (enrich / "scratch.txt").write_text("left over\n")
    (enrich / "watch.md").write_text(text, encoding="utf-8")
    return enrich


def test_seal_writes_the_pair_process_reads_and_removes_the_rest(mod, wiki, capsys):
    enrich = _notes(wiki, "- [00:10] A point\x00 with a \x1b[31mcontrol\n")
    assert mod.main(["seal", "--capture-dir", LEAF, "--model", "sonnet-x"]) == 0
    assert sorted(p.name for p in enrich.iterdir()) == ["watch.json", "watch.md"]
    assert (enrich / "watch.md").read_text() == "- [00:10] A point with a [31mcontrol\n"
    meta = json.loads((enrich / "watch.json").read_text())
    assert {k: meta[k] for k in ("v", "engine", "unit", "model", "tokens", "frames")} == {
        "v": 1, "engine": "local", "unit": mod.UNIT, "model": "sonnet-x", "tokens": None, "frames": 2,
    }
    assert "question" not in meta
    assert json.loads(capsys.readouterr().out)["frames"] == 2


def test_seal_without_a_model_names_none(mod, wiki):
    enrich = _notes(wiki, "- fine\n")
    mod.main(["seal", "--capture-dir", LEAF])
    assert json.loads((enrich / "watch.json").read_text())["model"] is None


@pytest.mark.parametrize("text", ["", "   \n\x00\n"])
def test_seal_refuses_notes_that_are_empty_and_touches_nothing(mod, wiki, capsys, text):
    enrich = _notes(wiki, text)
    assert mod.main(["seal", "--capture-dir", LEAF]) == 1
    assert "write the notes first" in capsys.readouterr().err
    assert (enrich / "frames.json").is_file() and not (enrich / "watch.json").exists()


def test_seal_refuses_when_no_notes_were_written(mod, wiki):
    assert mod.main(["seal", "--capture-dir", LEAF]) == 1


def test_a_notes_file_past_the_ceiling_is_cut(mod, wiki):
    enrich = _notes(wiki, "x" * (mod.MAX_NOTES_CHARS + 500))
    mod.main(["seal", "--capture-dir", LEAF])
    assert len((enrich / "watch.md").read_text()) == mod.MAX_NOTES_CHARS + 1


@pytest.mark.parametrize("given", ["/etc", "../outside", "a/../../b"])
def test_a_capture_dir_that_is_not_wiki_relative_is_refused(mod, wiki, given):
    with pytest.raises(SystemExit) as exc:
        mod.main(["seal", "--capture-dir", given])
    assert "WIKI-RELATIVE" in str(exc.value)


def _target(wiki):
    other = wiki / "other"
    other.mkdir()
    (other / "precious.txt").write_text("keep")
    return other


def test_seal_refuses_a_symlinked_enrich_directory_and_touches_what_it_points_at(mod, wiki, capsys):
    other = _target(wiki)
    (other / "watch.md").write_text("- looks like notes\n")
    (wiki / LEAF / "enrich").symlink_to(other, target_is_directory=True)
    assert mod.main(["seal", "--capture-dir", LEAF]) == 1
    assert "symlink" in capsys.readouterr().err
    assert sorted(p.name for p in other.iterdir()) == ["precious.txt", "watch.md"]


def test_seal_refuses_a_symlinked_notes_file(mod, wiki):
    enrich = _notes(wiki, "- fine\n")
    (enrich / "watch.md").unlink()
    secret = wiki / "secret.txt"
    secret.write_text("a secret")
    (enrich / "watch.md").symlink_to(secret)
    assert mod.main(["seal", "--capture-dir", LEAF]) == 1
    assert not (enrich / "watch.json").exists()


def test_seal_removes_a_symlink_among_the_rest_without_following_it(mod, wiki):
    other = _target(wiki)
    enrich = _notes(wiki, "- fine\n")
    (enrich / "link").symlink_to(other, target_is_directory=True)
    assert mod.main(["seal", "--capture-dir", LEAF]) == 0
    assert sorted(p.name for p in enrich.iterdir()) == ["watch.json", "watch.md"]
    assert [p.name for p in other.iterdir()] == ["precious.txt"]


def test_frames_replaces_a_symlinked_enrich_directory_and_never_writes_through_it(mod, wiki, ytdlp, capsys):
    other = _target(wiki)
    (wiki / LEAF / "enrich").symlink_to(other, target_is_directory=True)
    ytdlp.set(fail="ERROR: unable to download: HTTP Error 503\n")
    with pytest.raises(SystemExit):
        frames(mod)
    assert not (wiki / LEAF / "enrich").exists() and [p.name for p in other.iterdir()] == ["precious.txt"]
