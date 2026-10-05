"""channel-substack, the harness tier: the unit installed and enabled through the REAL
CLI, each stage started by the runner in the jail it composes, with the
harness profile's fake agent typing what the unit's SKILL.md says. Its
helpers and constants are the unit's own tests' —
`skills/channel-substack/tests/test_substack.py`, which ships with the unit —
so a case here reads exactly as it did beside them.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess

from harness import RESOLVABLE_TEST_HOST, claimed, declared_job, pending, rooted, staged, unit_tests

# The unit's own helpers, constants and fixtures — the stdlib above is this file's.
globals().update(unit_tests("channel-substack", "test_substack"))

SCRIPT = "ops/skills/channel-substack/scripts"


def harvested(ops, env, wiki, job, newsletter: str, leaves: list, pages: dict, reports: int = 1):
    """The harvest stage, in its jail: step 1's `leaves.json` (the enumerator
    reads the archive API, which nothing here reaches), each post's page as a
    fetch leaves it, then `capture_posts.py` and its `--report`."""
    ticket_id, cap = claimed(ops, env, wiki, job)
    doc = {"v": 1, "slug": job.slug, "newsletter": newsletter, "capture_dir": str(cap.relative_to(wiki)),
           "leaves": leaves, "summary": {"truncated": False}}
    files = {"leaves.json": json.dumps(doc).encode()}
    fetched = ""
    for i, (directory, html) in enumerate(pages.items()):
        files[f"page-{i}.html"] = html
        fetched += f'mkdir -p {shlex.quote(directory)} && cp "$FIX/page-{i}.html" {shlex.quote(directory)}/page.html\n'
    report = "".join(f'step report-{n} "$OPS" run {SCRIPT}/capture_posts.py --capture-dir "$CAP" --report --ticket "$TICKET"\n'
                     for n in range(reports))  # a respawned worker reports again: same names
    session = staged(ops, env, wiki, ticket_id, f"""\
cp "$FIX/leaves.json" "$CAP/leaves.json"
{fetched}step capture "$OPS" run {SCRIPT}/capture_posts.py --capture-dir "$CAP"
{report}""", files=files)
    for name in ("capture", *(f"report-{n}" for n in range(reports))):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    assert session.update["status"] in ("ok", "partial"), session.update
    return cap


def paged(ops, env, wiki, job, capture_dir):
    """The process stage the harvest's landing minted for one post, in its
    jail, exactly as SKILL.md prescribes it: convert the captured `page.html`
    into `page create`'s stdin, `page edit … extracted=true`, then report.
    Returns the page."""
    record = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    said = json.loads((capture_dir / "leaf.json").read_text(encoding="utf-8"))
    page = f"{job.dest}/{record['title'].strip()}.md"
    keys = [f"title={record['title']}", f"dest={job.dest}", f"resource={record['item']}", "type=article"]
    keys += [f"published={said['published']}"] if said.get("published") else []
    keys += [f"audience={said['audience']}"] if said.get("audience") else []
    # The documented lines, as a worker TYPES them: every venue value single-quoted,
    # so every content case is a quoting case too.
    quoted = " ".join(f"'{k}'" for k in keys)
    create = (f"\"$OPS\" run {SCRIPT}/to_markdown.py \"$CAP/page.html\" --out - --selector .available-content "
              f"--base-url '{record['item']}' | \"$OPS\" page create {quoted} --stdin")
    process_id = pending(ops, env, wiki, job.slug)[str(capture_dir.relative_to(wiki))]
    session = staged(ops, env, wiki, process_id, f"""\
step create sh -c {shlex.quote(create)}
step extracted sh -c {shlex.quote(f"\"$OPS\" page edit '{page}' extracted=true")}
printf '%s' {shlex.quote(json.dumps([page]))} > "$CAP/written.json"
step update "$OPS" --json pipeline tickets update "$TICKET" stage=process status=ok written_from=written.json
""")
    for name in ("create", "extracted", "update"):
        done = session.step(name)
        assert done.returncode == 0, (name, done.stdout + done.stderr)
    return wiki / page


def _hostile_page():
    html = (FIX / "post-the-newest-one.html").read_text(encoding="utf-8")
    return html.replace('name="author" content="Ada Example"', 'name="author" content="Ada Example&#10;&#10;## Forged by the author&#10;&#10;```"')


def _leaf_dir(job, item: str, name: str) -> str:
    return f"_raw/{job.slug}/p-{name}--{hashlib.sha1(item.encode()).hexdigest()[:8]}"


def test_one_ticket_lands_every_free_post_as_a_staged_page(ops, env, wiki, monkeypatch, capsys, tmp_path):
    """The whole point of the rework: a harvest ticket planned by the real
    enumerator, captured in its jail, and its `--report` posting `tickets
    update` through the REAL CLI; one process ticket per post, each a page."""
    # The runner refuses a ticket whose target host does not resolve to a public
    # address; `ARCHIVE`'s own (`example-newsletter.invalid`) never does, so the
    # job's target is `RESOLVABLE_TEST_HOST`. The enumerator runs here, in
    # process, over the fixture archive with the API stubbed: its ticket names
    # `ARCHIVE`, the host the fixture's posts are canonicalized under.
    job = declared_job(ops, env, wiki, UNIT, f"https://{RESOLVABLE_TEST_HOST}/archive")
    assert job.record["harvest"]["scope"] == "domain"  # the manifest's default, which the unit applies itself
    plan = _plan(monkeypatch, capsys, tmp_path / "plan", _ticket(slug=job.slug), "--out", "leaves.json")
    assert set(_slugs(plan)) <= {"the-newest-one", "a-podcast-episode", "sponsored-roundup", "already-held", "ancient-history"}
    pages = {leaf["dir"]: (FIX / f"post-{leaf['item'].rsplit('/', 1)[-1]}.html").read_bytes() for leaf in plan["leaves"]
             if (FIX / f"post-{leaf['item'].rsplit('/', 1)[-1]}.html").is_file()}
    harvested(ops, env, wiki, job, plan.get("newsletter", ARCHIVE), plan["leaves"], pages)

    captured_dirs = [leaf["dir"] for leaf in plan["leaves"] if (wiki / leaf["dir"] / "capture.json").is_file()]
    assert captured_dirs, "nothing captured"
    record = json.loads((wiki / captured_dirs[0] / "capture.json").read_text(encoding="utf-8"))
    # Harvest is BYTES: the page as it arrived, and no page's keys on the record.
    assert record["body"] == "page.html" and record["content_type"] == "text/html" and record["slug"] == job.slug
    assert set(record) == {"v", "slug", "item", "title", "body", "content_type", "fetched_at"}

    # Landing mints one process ticket per captured dir; each is one build.
    assert sorted(pending(ops, env, wiki, job.slug)) == sorted(captured_dirs)
    pages = [paged(ops, env, wiki, job, wiki / d) for d in captured_dirs]
    assert pages and len(set(pages)) == len(pages)
    assert all(page.is_relative_to(wiki / job.dest) and page.is_file() for page in pages)


def test_two_posts_with_one_title_land_as_two_pages(ops, env, wiki):
    """A page is filed under its title, and the second write of a name takes the
    first's file: before the report settled titles, a newsletter's second "Open
    Thread" WAS the first one's page, and both process tickets said ok."""
    # Nothing fetches `host` — `capture_posts.py` reads the `leaves.json` and
    # `page.html` the plan hands it — so it need only resolve: `RESOLVABLE_TEST_HOST`.
    bare_host = RESOLVABLE_TEST_HOST
    host = f"https://{bare_host}"
    job = declared_job(ops, env, wiki, UNIT, f"{host}/archive-names", slug="port-channel-substack-names")
    leaves, pages = [], {}
    for name, published, fixture in (("open-thread-2", "2026-09-10", "the-newest-one"), ("open-thread", "2026-08-13", "a-podcast-episode")):
        item = f"{host}/p/{name}"
        rel = _leaf_dir(job, item, name)
        pages[rel] = (FIX / f"post-{fixture}.html").read_bytes()
        leaves.append({"item": item, "dir": rel, "title": "Open Thread", "published": published, "audience": "everyone", "on_disk": False})
    harvested(ops, env, wiki, job, bare_host, leaves, pages, reports=2)

    captured_dirs = [leaf["dir"] for leaf in leaves if (wiki / leaf["dir"] / "capture.json").is_file()]
    pages = [paged(ops, env, wiki, job, wiki / d) for d in captured_dirs]
    assert len({page.resolve() for page in pages}) == 2 and all(page.is_relative_to(wiki / job.dest) for page in pages)
    assert sorted(page.name for page in pages) == ["Open Thread (2026-08-13).md", "Open Thread.md"]


# --- Rule 1: the title is a legal filename ------------------------------------
def test_a_title_the_host_would_refuse_still_lands_and_forges_nothing(ops, env, wiki):
    """Rule 1 + Rule 2, through the REAL `page create`. Before the fix the raw
    title went into `capture.json`, harvest said ok, and the process ticket was
    refused: "a title cannot carry ':'"."""
    # See test_two_posts_with_one_title_land_as_two_pages: resolvable, not reachable.
    bare_host = RESOLVABLE_TEST_HOST
    host = f"https://{bare_host}"
    job = declared_job(ops, env, wiki, UNIT, f"{host}/archive-titles", slug="port-channel-substack-titles")
    leaves, pages = [], {}
    # The second differs from the first ONLY in characters the host refuses:
    # they collide once both are made safe, which is why safe_title runs first.
    for name, title, published in (("lesson-3", HOSTILE_TITLE, "2026-09-10"), ("lesson-3b", 'Lesson 3: What is "A|B" testing*', "2026-09-03\n# Forged date")):
        item = f"{host}/p/{name}"
        rel = _leaf_dir(job, item, name)
        pages[rel] = _hostile_page().encode()
        leaves.append({"item": item, "dir": rel, "title": title, "published": published, "audience": "everyone", "on_disk": False})
    harvested(ops, env, wiki, job, bare_host, leaves, pages)

    record0 = json.loads((wiki / leaves[0]["dir"] / "capture.json").read_text(encoding="utf-8"))
    assert record0["title"] == "Lesson 3 - What is ’A-B’ testing # Forged heading ---"
    said = json.loads((wiki / leaves[0]["dir"] / "leaf.json").read_text(encoding="utf-8"))
    assert said["title"] == '.Lesson 3: What is "A/B" testing? # Forged heading ---'  # the true one, on one line
    second = json.loads((wiki / leaves[1]["dir"] / "leaf.json").read_text(encoding="utf-8"))
    assert second["published"] is None  # `2026-09-03\n# Forged date` is no date: dropped, never passed on

    captured_dirs = [leaf["dir"] for leaf in leaves if (wiki / leaf["dir"] / "capture.json").is_file()]
    pages = [paged(ops, env, wiki, job, wiki / d) for d in captured_dirs]
    assert pages and all(page.is_file() for page in pages)
    lines = pages[0].read_text(encoding="utf-8").splitlines()
    # the venue's title reaches the page QUOTED, opening no heading and no rule of its own
    assert lines[1] == "title: 'Lesson 3 - What is ’A-B’ testing # Forged heading ---'"
    assert "# Forged heading" not in lines and "# Forged date" not in lines
    assert [line for line in lines if line.strip() == "---"] == ["---", "---"]  # the page's own block only
    assert "lighthouses" in "\n".join(lines)


def test_a_hundred_cjk_characters_land_and_so_does_their_namesake(ops, env, wiki):
    """The host's `filename_for` checks no LENGTH: 100 CJK characters are 300
    bytes and the write died `OSError: File name too long`. The cap is held in
    UTF-8 bytes — and the report's de-dup qualifier, added AFTER it, still
    fits: this unit's qualifiers are a date, a hash8 and a counter."""
    # See test_two_posts_with_one_title_land_as_two_pages: resolvable, not reachable.
    bare_host = RESOLVABLE_TEST_HOST
    host = f"https://{bare_host}"
    job = declared_job(ops, env, wiki, UNIT, f"{host}/archive-cjk", slug="port-channel-substack-cjk")
    leaves, pages = [], {}
    for name, published in (("cjk-2", "2026-09-10"), ("cjk-1", "2026-09-03")):
        item = f"{host}/p/{name}"
        rel = _leaf_dir(job, item, name)
        pages[rel] = (FIX / "post-the-newest-one.html").read_bytes()
        leaves.append({"item": item, "dir": rel, "title": "語" * 100, "published": published, "audience": "everyone", "on_disk": False})
    harvested(ops, env, wiki, job, bare_host, leaves, pages)

    record0 = json.loads((wiki / leaves[0]["dir"] / "capture.json").read_text(encoding="utf-8"))
    record1 = json.loads((wiki / leaves[1]["dir"] / "capture.json").read_text(encoding="utf-8"))
    first, second = record0["title"], record1["title"]
    assert first.endswith("…") and len(first.encode()) <= 203 and second == f"{first} (2026-09-03)"
    captured_dirs = [leaf["dir"] for leaf in leaves]
    pages = [paged(ops, env, wiki, job, wiki / d) for d in captured_dirs]
    assert [page.name for page in pages] == [f"{first}.md", f"{second}.md"] and all(page.is_file() for page in pages)
    assert max(len(page.name.encode()) for page in pages) <= 255  # what the write dies on


def test_a_title_with_an_apostrophe_survives_the_documented_shell_line(ops, env, wiki):
    """The process step is a shell line a worker TYPES, single-quoting the title
    off `capture.json`. `safe_title` maps BOTH quote forms to U+2019, so no
    title it can produce breaks out of those quotes and loses its page."""
    dest = "sources/scrapes/port-substack-apostrophe"
    for venue in ("Don't Panic", 'He said "no" twice'):
        title = _module("capture_posts").safe_title(venue)
        assert "'" not in title, title
        line = (
            "printf '%s' 'body' | "
            + shlex.join([*ops, "--json", "page", "create"])
            + f" 'title={title}' 'dest={dest}' 'resource=https://example.invalid/x'"
            + f" 'extracted=true' 'type=article' --stdin"
        )
        done = subprocess.run(["/bin/sh", "-c", line], env=rooted(env, wiki), capture_output=True, text=True, check=False)
        assert done.returncode == 0, line + "\n" + done.stdout + done.stderr
        assert (wiki / json.loads(done.stdout)["path"]).is_file()
