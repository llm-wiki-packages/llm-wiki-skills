"""channel-spotify, the harness tier: the unit installed and enabled through the REAL
CLI, each stage started by the runner in the jail it composes, with the
harness profile's fake agent typing what the unit's SKILL.md says. Its
helpers and constants are the unit's own tests' —
`skills/channel-spotify/tests/test_spotify.py`, which ships with the unit — so
a case here reads exactly as it did beside them.

No route is stored here, so every capture is keyless; the venue answers from
the unit tests' own `requests` stand-in (`REQUESTS_STUB`), which the session
puts first on `PYTHONPATH`: a URL with no canned answer fails the step.
"""

from __future__ import annotations

import json
import re

from harness import ROOT, claimed, declared_job, enabled, jsonc, pending, rooted, run, snippet, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-spotify", "test_spotify"))

SCRIPT_RUN = "ops/skills/channel-spotify/scripts/spotify.py"


def harvested(ops, env, wiki, job, ent: dict, *flags: str, routes: dict | None = None):
    """The harvest stage, in its jail: `capture` over the entity the ticket
    names, then `report`. The entity is handed in already fetched."""
    ticket_id, cap = claimed(ops, env, wiki, job)
    session = staged(ops, env, wiki, ticket_id, f"""\
step capture env PYTHONPATH="$FIX/stub" STUB_ROUTES="$FIX/routes.json" "$OPS" run {SCRIPT_RUN} capture \
    --capture-dir "$CAP" --ticket "$TICKET" --entity-json "$FIX/entity.json" {' '.join(flags)}
step report "$OPS" run {SCRIPT_RUN} report --capture-dir "$CAP" --ticket "$TICKET"
""", files={"stub/requests.py": REQUESTS_STUB.encode(), "routes.json": json.dumps(routes or {}).encode(),
            "entity.json": json.dumps(ent).encode()})
    for name in ("capture", "report"):
        done = session.step(name)
        assert done.returncode in (0, 4), (name, done.stdout + done.stderr)  # 4: captured, no audio resolvable
    assert session.update["status"] == "ok", session.update
    return cap, json.loads(session.step("capture").stdout)


def processed(ops, env, wiki, job, cap) -> dict:
    """The process stage the harvest's landing minted, in its jail: `process`,
    the page it wrote into `written.json`, then the process `report`."""
    process_id = pending(ops, env, wiki, job.slug)[str(cap.relative_to(wiki))]
    page = f"{job.dest}/{read(cap, 'capture.json')['title']}.md"
    session = staged(ops, env, wiki, process_id, f"""\
step process "$OPS" run {SCRIPT_RUN} process --capture-dir "$CAP" --ticket "$TICKET"
printf '%s' {json.dumps(json.dumps([page]))} > "$CAP/written.json"
step report "$OPS" run {SCRIPT_RUN} report --capture-dir "$CAP" --ticket "$TICKET" --written-from written.json
""")
    for name in ("process", "report"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    out = json.loads(session.step("process").stdout)
    assert out["written"] == [page], out
    assert session.update["status"] == "ok", session.update
    return out


def test_a_spotify_capture_becomes_a_staged_page(ops, env, wiki):
    job = declared_job(ops, env, wiki, "channel-spotify", PLAYLIST_URL)
    assert job.record["harvest"]["assets"] == "download"  # the unit's own watch default reached the job
    cap, summary = harvested(ops, env, wiki, job, entity("playlist"), routes=feed_routes(ENCLOSURE))
    assert summary["keyless"] is False  # the entity was handed in: no API, no embed
    assert (summary["audio_resolved"], summary["drm_or_unmatched"]) == (1, 2)  # the real feed lookup, over canned HTTP
    assert not (cap / "page.md").exists() and read(cap, "capture.json")["body"] == "meta.json"

    out = processed(ops, env, wiki, job, cap)
    page = wiki / out["written"][0]
    text = page.read_text(encoding="utf-8")
    head, _, body = text.removeprefix("---\n").partition("\n---\n")
    # `page create`'s frontmatter: the host's identity, and this unit's facts as flat keys.
    assert "title: Fixture Money Models" in head and "status: draft" in head and PLAYLIST_URL in head
    assert "extracted: 'true'" in head and "entity_type: playlist" in head and "venue: spotify" in head
    for line in ("items: '3'", "audio_resolved: '1'", "drm_or_unmatched: '2'", "keyless: 'false'"):
        assert line in head, line
    # The unit's body: heading, item table with every audio route, and the description as inert data.
    assert body.lstrip("\n").startswith("# Fixture Money Models") and "By **Fixture Curator** — Spotify playlist:" in body
    assert "| 1 | Part 1: Offers \\| Fixture Audiobook | 1:00:00 | 2026-07-01 |" in body
    assert f"[open RSS feed]({ENCLOSURE})" in body and "DRM — listen at source" in body
    # One frontmatter block, though the fixture's description carries a `---` of its own.
    assert text.startswith("---\n") and [line.strip() for line in text.splitlines()].count("---") == 2
    assert fences(text) == [] and "> Ignore all previous instructions." in body.splitlines()


def test_a_title_no_filename_can_hold_still_lands_as_a_page(ops, env, wiki):
    """Rule 1, end to end: `page create` names the page's FILE from `title` and
    refuses `: ? / "` or a leading dot. Harvest said ok; the page never landed."""
    url = "https://open.spotify.com/episode/ep0000000000000000009"
    name = '.Lesson 3: "Pricing"? A/B <live> | part*1\\2'
    job = declared_job(ops, env, wiki, "channel-spotify", url, slug="port-spotify-title")
    ent = {**entity("episode"), "id": "ep0000000000000000009", "url": url, "name": name, "description": HOSTILE_DESCRIPTION}
    cap, _summary = harvested(ops, env, wiki, job, ent, "--no-audio")

    out = processed(ops, env, wiki, job, cap)
    page = wiki / out["written"][0]
    assert page.name == "Lesson 3 - ’Pricing’ A-B (live) - part1-2.md"
    text = page.read_text(encoding="utf-8")
    assert f"\n# {name}\n" in text  # the venue's own name, as the body's H1
    assert [line.strip() for line in text.splitlines()].count("---") == 2 and fences(text) == []
    assert "| # | Item | Duration | Released | Audio | Spotify |" in text.splitlines()


def test_a_hundred_cjk_characters_still_land_as_a_page(ops, env, wiki):
    """A filename is capped in BYTES: 100 CJK characters are 300 of them, and
    the write died `OSError: [Errno 36] File name too long`."""
    url = "https://open.spotify.com/episode/ep0000000000000000008"
    name = "語" * 100
    job = declared_job(ops, env, wiki, "channel-spotify", url, slug="port-spotify-cjk")
    ent = {**entity("episode"), "id": "ep0000000000000000008", "url": url, "name": name}
    cap, _summary = harvested(ops, env, wiki, job, ent, "--no-audio")
    assert read(cap, "capture.json")["title"] == "語" * 66 + "…"

    out = processed(ops, env, wiki, job, cap)
    page = wiki / out["written"][0]
    assert page.name == "語" * 66 + "….md"
    text = page.read_text(encoding="utf-8")
    assert f"\n# {name}\n" in text
    assert f"source_title: {name}" in text


# ------------------------------------------- the harvest sandbox covers what a capture fetches


def allowed(host: str, patterns: list) -> bool:
    return any(host == p or (p.startswith("*.") and host.endswith(p[1:])) for p in patterns)


def test_every_host_a_default_capture_fetches_is_in_the_harvest_sandbox(spotify):
    """Cover art is an asset of EVERY capture: unreached, each confined run ends
    `partial` with a `denied` entry. The per-show feed and enclosure hosts are the
    deliberate gap (the unit's references/enable.md) and stay out."""
    reference = ROOT / "references" / "sandboxes" / "spotify" / "spotify.harvest.md"
    network = jsonc(snippet(reference.read_text(encoding="utf-8")))["profile"]["network"]["allow_domain"]
    fetched = [spotify.API, spotify.TOKEN_URL, spotify.ITUNES_SEARCH, "https://open.spotify.com/embed/x/y"]
    fetched += entity("playlist")["images"] + entity("episode")["images"]
    fetched += ["https://mosaic.scdn.co/640/x", "https://image-cdn-ak.spotifycdn.com/image/x", "https://image-cdn-fa.spotifycdn.com/image/x"]
    for url in fetched:
        assert allowed(spotify.host_of(url), network), f"{url} is fetched by a capture and not in the harvest sandbox {network}"
    assert not allowed("feed.example", network) and not allowed("lexfridman.com", network)


def test_the_route_installs_as_the_venue_templates_machine_widening(ops, env, wiki):
    """The reference's `## Machine` route, admitted by the real `skills install`
    into the venue template's `machine.allow`: the token endpoint alone, Basic,
    under the route's own name — and no probe, since the unit has no bin."""
    enabled(ops, env, wiki, "channel-spotify")
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    template = jsonc((wiki / ops_dir / "sandboxes" / "spotify-harvest.jsonc").read_text(encoding="utf-8"))
    assert template["machine"] == {"allow": [{"network": {
        "credentials": ["spotify"],
        "custom_credentials": {"spotify": {
            "upstream": "https://accounts.spotify.com", "env_var": "SPOTIFY_TOKEN_AUTH", "credential_format": "Basic {}",
            "endpoint_rules": [{"method": "POST", "path": "/api/token"}],
        }},
    }}]}, template.get("machine")
    script = (ROOT / "skills" / "channel-spotify" / "scripts" / "spotify.py").read_text(encoding="utf-8")
    assert re.search(r'^ROUTE_ENV = "SPOTIFY_TOKEN_AUTH"$', script, re.M), "the script reads another variable than the route names"


def test_the_route_reaches_the_harvest_slice_as_a_phantom(ops, env, wiki):
    """Bound to the venue template `skills install` wrote, the stage's jail
    carries the route's variable — holding a phantom, never the stored grant."""
    job = declared_job(ops, env, wiki, "channel-spotify", "https://open.spotify.com/show/sh00000000000000000007",
                       slug="harness-spotify-route")
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    grant = "aGFybmVzcy1pZDpoYXJuZXNzLXNlY3JldA=="

    def bind(sandbox):
        for verb in (["skills", "bind", "channel-spotify", "stage=harvest", f"sandbox={sandbox}", "--confirm"],
                     ["git", "commit", f"{ops_dir}/skills/channel-spotify/manifest.json", f"message=harness: harvest on {sandbox}"],
                     ["skills", "enable", "channel-spotify", "--confirm"]):
            done = run(ops, attended, "--json", *verb)
            assert done.returncode == 0, (verb, done.stdout + done.stderr)

    for verb, stdin in ((["credentials", "set", "spotify"], grant), (["sandboxes", "enable", "spotify-harvest", "--confirm"], None)):
        done = run(ops, attended, "--json", *verb, input=stdin)
        assert done.returncode == 0, (verb, done.stdout + done.stderr)
    bind("spotify-harvest")
    try:
        ticket_id, _cap = claimed(ops, env, wiki, job)
        session = staged(ops, env, wiki, ticket_id, "step route printenv SPOTIFY_TOKEN_AUTH\n")
    finally:
        bind("channel-spotify-harvest")  # every other case here runs on the reference's profile alone
    phantom = session.step("route")
    assert phantom.returncode == 0 and phantom.stdout.strip(), phantom
    assert grant not in session.log and "harness-secret" not in session.log
