"""channel-github's scripts against fixtures — never the CLI, never the network."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"


# The scripts import their siblings (`door`, `catalog`) by name, as `run` does.
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(f"gh_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


harvest = _load("harvest")
page = _load("page")
lists = _load("lists")

OPTS = dict(harvest.DEFAULTS)


def raw_repo(full, stars=100, **kw):
    owner, name = full.split("/")
    return {
        "full_name": full,
        "name": name,
        "owner": {"login": owner},
        "html_url": f"https://github.com/{full}",
        "description": kw.get("description", "A thing."),
        "stargazers_count": stars,
        "forks_count": 3,
        "language": "Python",
        "topics": kw.get("topics", ["agents"]),
        "license": {"spdx_id": "MIT"},
        "archived": kw.get("archived", False),
        "fork": kw.get("fork", False),
        "created_at": "2024-01-02T00:00:00Z",
        "pushed_at": kw.get("pushed_at", "2026-09-30T00:00:00Z"),
        "homepage": "",
    }


# ------------------------------------------------------------------ selectors


def test_selectors_parse_every_kind():
    got = harvest.parse_selectors("stars:octocat, org:example-org\nrepo:a/b,user:x,search:topic:mcp stars:>100")
    assert got == [("stars", "octocat"), ("org", "example-org"), ("repo", "a/b"), ("user", "x"), ("search", "topic:mcp stars:>100")]


@pytest.mark.parametrize("bad", ["", "stars", "bogus:x", "repo:nope", "org:a b", "repo:a/b/c"])
def test_selectors_refuse_bad_entries(bad):
    with pytest.raises(ValueError):
        harvest.parse_selectors(bad)


# ------------------------------------------------------------------ the repo


def test_normalize_and_title():
    r = harvest.normalize(raw_repo("example-org/agent-kit", 5000), via="stars:me", starred_at="2025-03-01T10:00:00Z")
    assert r["url"] == "https://github.com/example-org/agent-kit"
    assert r["starred_at"] == "2025-03-01" and r["created"] == "2024-01-02" and r["license"] == "MIT"
    assert harvest.page_title(r["full_name"]) == "example-org--agent-kit"


def test_merge_unions_selectors_and_keeps_starred():
    seen = {}
    harvest.merge_repo(seen, harvest.normalize(raw_repo("a/B"), via="org:a"))
    harvest.merge_repo(seen, harvest.normalize(raw_repo("a/B"), via="stars:me", starred_at="2025-01-01T00:00:00Z"))
    (r,) = seen.values()
    assert r["via"] == ["org:a", "stars:me"] and r["starred_at"] == "2025-01-01"


def test_forks_dropped_from_org_but_never_from_stars():
    fork = harvest.normalize(raw_repo("a/f", fork=True), via="org:a")
    assert not harvest.keep(fork, OPTS, "org")
    assert harvest.keep(fork, OPTS, "stars")


# ------------------------------------------------------------------ change


def repo(stars=1000, **kw):
    r = harvest.normalize(raw_repo("a/b", stars, **kw), via=kw.get("via", "stars:me"), starred_at=kw.get("starred"))
    return r


def test_new_when_unheld():
    assert harvest.decide(repo(), None, False, OPTS, "2026-10-09") == "new"


def test_held_by_page_never_captured_is_baseline_only():
    assert harvest.decide(repo(), None, True, OPTS, "2026-10-09") is None


def test_jump_absolute_and_percent():
    prev = {"captured_at": "2026-09-01", "stars_at_capture": 1000, "via": ["stars:me"]}
    assert harvest.decide(repo(1200), prev, True, OPTS, "2026-10-09") is None  # +20%, +200
    assert harvest.decide(repo(1250), prev, True, OPTS, "2026-10-09") == "jump"  # +25%
    big = {"captured_at": "2026-09-01", "stars_at_capture": 100000, "via": ["stars:me"]}
    assert harvest.decide(repo(100500), big, True, OPTS, "2026-10-09") == "jump"  # +500 absolute
    small = {"captured_at": "2026-09-01", "stars_at_capture": 200, "via": ["stars:me"]}
    assert harvest.decide(repo(260), small, True, OPTS, "2026-10-09") == "jump"  # +30%, +60
    tiny = {"captured_at": "2026-09-01", "stars_at_capture": 10, "via": ["stars:me"]}
    assert harvest.decide(repo(40), tiny, True, OPTS, "2026-10-09") is None  # +300% but under the floor


def test_newly_starred_and_new_selector_and_stale():
    prev = {"captured_at": "2026-09-01", "stars_at_capture": 1000, "via": ["org:a"]}
    assert harvest.decide(repo(starred="2026-10-01T00:00:00Z", via="org:a"), prev, True, OPTS, "2026-10-09") == "starred"
    assert harvest.decide(repo(via="org:b"), prev, True, OPTS, "2026-10-09") == "via"
    old = {"captured_at": "2026-01-01", "stars_at_capture": 1000, "via": ["stars:me"]}
    assert harvest.decide(repo(pushed_at="2026-09-30T00:00:00Z"), old, True, OPTS, "2026-10-09") == "stale"
    assert harvest.decide(repo(pushed_at="2025-12-01T00:00:00Z"), old, True, OPTS, "2026-10-09") is None


def test_leaf_names_stable_and_dated():
    url = "https://github.com/example-org/agent-kit"
    assert harvest.leaf_name(url).startswith("example-org-agent-kit--")
    assert harvest.leaf_name(url, "2026-10-09").endswith("-20261009")


def test_history_one_per_day_capped():
    e = {"history": [["2026-10-0%d" % i, i] for i in range(1, 10)] + [["2026-10-10", 5], ["2026-10-11", 6], ["2026-10-12", 7]]}
    h = harvest.record_history(e, 8, "2026-10-12")
    assert h[-1] == ["2026-10-12", 8] and len(h) == harvest.HISTORY_MAX
    assert harvest.record_history(e, 9, "2026-10-13")[-1] == ["2026-10-13", 9]


# ------------------------------------------------------------------ a whole run


class FakeHeaders(dict):
    def get(self, k, d=None):
        return super().get(k, d)


def test_whole_run_captures_then_skips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    starred = [
        {"starred_at": "2026-10-01T00:00:00Z", "repo": raw_repo("a/one", 900)},
        {"starred_at": "2026-09-01T00:00:00Z", "repo": raw_repo("b/two", 50)},
    ]
    calls, updates = [], []

    def fake_get(url, token, accept="application/vnd.github+json"):
        calls.append(url)
        if "/starred" in url:
            return json.dumps(starred).encode(), FakeHeaders()
        if url.endswith("/readme"):
            if "b/two" in url:
                raise harvest.NotFound(url)
            return b"# One\n\nHello.", FakeHeaders()
        raise AssertionError(url)

    ticket = {"ticket": "t1", "slug": "github-stars", "capture_dir": "_raw/github-stars/2026-10-09",
              "options": {"select": "stars:me"}, "known": [], "credential": {}, "credential_mode": "none"}
    monkeypatch.setattr(harvest, "_get", fake_get)
    monkeypatch.setattr(harvest, "open_ticket", lambda t, s=None: ticket)
    monkeypatch.setattr(harvest, "post_update", lambda *a, **k: updates.append((a, k)) or 0)
    assert harvest.run("t1") == 0
    (args, kw), = updates
    assert args[2] == "ok" and len(kw["captured"]) == 2
    leaf = tmp_path / kw["captured"][0]
    cap = json.loads((leaf / "capture.json").read_text())
    assert cap["title"] == "a--one" and cap["body"] == "README.md" and cap["item"] == "https://github.com/a/one"
    no_readme = json.loads((tmp_path / kw["captured"][1] / "capture.json").read_text())
    assert no_readme["body"] == "repo.json"
    state = json.loads((tmp_path / "_raw/github-stars/.state.json").read_text())
    assert state["repos"]["a/one"]["stars_at_capture"] == 900

    # Second run, same stars: nothing changed, nothing captured.
    updates.clear()
    ticket["known"] = [{"resource": "https://github.com/a/one"}, {"resource": "https://github.com/b/two"}]
    assert harvest.run("t1") == 0
    (args, kw), = updates
    assert args[2] == "ok" and kw["captured"] == [] and "nothing changed" in kw["reason"]

    # Third run, a/one jumped: one dated update leaf, carrying prev.
    updates.clear()
    starred[0]["repo"]["stargazers_count"] = 2000
    assert harvest.run("t1") == 0
    (args, kw), = updates
    assert len(kw["captured"]) == 1 and kw["captured"][0].endswith(tuple("0123456789"))
    facts = json.loads((tmp_path / kw["captured"][0] / "repo.json").read_text())
    assert facts["change"] == "jump" and facts["prev"]["stars"] == 900


def test_refused_update_keeps_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ticket = {"ticket": "t1", "slug": "s", "capture_dir": "_raw/s/d", "options": {"select": "repo:a/one"}, "known": []}
    monkeypatch.setattr(harvest, "_get", lambda url, token, accept=None: (json.dumps(raw_repo("a/one")).encode() if "/readme" not in url else b"x", FakeHeaders()))
    monkeypatch.setattr(harvest, "open_ticket", lambda t, s=None: ticket)
    monkeypatch.setattr(harvest, "post_update", lambda *a, **k: 1)
    assert harvest.run("t1") == 2
    assert not (tmp_path / "_raw/s/.state.json").exists()


# ------------------------------------------------------------------ the page


def facts(**kw):
    r = harvest.normalize(raw_repo("a/one", 12345, topics=["mcp", "agents"]), via="stars:me", starred_at="2025-03-01T00:00:00Z")
    r.update({"seen": "2026-10-09", "change": "new", "prev": None, **kw})
    return r


JUDGMENT = {"keep": True, "junk": None, "description": "An MCP server for [[Postgres]].", "summary": "Does X.",
            "use_for": ["query Postgres from an agent"], "categories": ["MCP Servers", "databases", "github"]}


def test_keys_carry_facts_signals_and_categories():
    k = page.page_keys(facts(), JUDGMENT, {}, clipped=False)
    assert k["type"] == "repo" and k["gh_stars"] == 12345 and k["gh_starred_at"] == "2025-03-01"
    assert k["tags"] == "github,gh-starred,mcp-servers,databases"
    assert k["description"] == "An MCP server for Postgres."
    assert k["gh_first_seen"] == "2026-10-09"
    assert "gh_archived" not in k and "gh_stars_prev" not in k


def test_keys_merge_held_tags_and_first_seen():
    held = {"tags": ["clip", "gh-clipped", "marketing"], "gh_first_seen": "2025-01-01"}
    k = page.page_keys(facts(via=["org:a"]), JUDGMENT, held, clipped=True)
    assert k["tags"].split(",") == ["gh-clipped", "marketing", "github", "gh-starred", "gh-watched", "mcp-servers", "databases"]
    assert k["gh_first_seen"] == "2025-01-01"


def test_body_keeps_notes_and_demotes_readme():
    readme = "# Title\n\n```sh\n# not a heading\n```\n\n## Install\n"
    body = page.render_body(facts(prev={"stars": 12000, "at": "2026-09-01"}), JUDGMENT, readme, "my note", False, "full")
    assert "★ 12,345 as of 2026-10-09 · +345 since 2026-09-01" in body
    assert "## Notes\n\nmy note" in body
    assert "### Title" in body and "# not a heading" in body and "#### Install" in body
    assert page.section(body, "## Notes") == "my note"
    assert page.section(body, "## What it's for") == "- query Postgres from an agent"


def test_readme_modes():
    long = "\n".join(f"line {i}" for i in range(400))
    assert page.readme_part(long, "none") == ""
    assert "truncated" in page.readme_part(long, "excerpt")
    assert page.readme_part("```\nopen", "excerpt").endswith("```")


def test_find_held_by_title_then_resource(tmp_path):
    dest = tmp_path / "sources/github"
    dest.mkdir(parents=True)
    assert page.find_held(dest, "a--one", "https://github.com/a/one") is None
    clip = dest / "Some Clipped Name.md"
    clip.write_text('---\ntype: repo\nresource: "https://github.com/A/One/"\n---\nbody\n')
    assert page.find_held(dest, "a--one", "https://github.com/a/one") == clip
    direct = dest / "a--one.md"
    direct.write_text("---\ntype: repo\n---\n")
    assert page.find_held(dest, "a--one", "https://github.com/a/one") == direct


# ------------------------------------------------------------------ credential


def test_keyless_unless_the_route_is_filled(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "phantom")
    monkeypatch.delenv("LLM_WIKI_CREDENTIAL_MODE", raising=False)
    assert harvest.get_token({"credential_mode": "none"}) is None
    assert harvest.get_token({}) is None
    assert harvest.get_token({"credential_mode": "route"}) == "phantom"
    monkeypatch.setenv("LLM_WIKI_CREDENTIAL_MODE", "route")
    assert harvest.get_token({}) == "phantom"


def test_route_mode_with_no_phantom_fails_the_ticket_as_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    ticket = {"ticket": "t1", "slug": "s", "capture_dir": "_raw/s/d", "options": {"select": "repo:a/one"}, "known": [], "credential_mode": "route"}
    updates = []
    monkeypatch.setattr(harvest, "open_ticket", lambda t, s=None: ticket)
    monkeypatch.setattr(harvest, "post_update", lambda *a, **k: updates.append((a, k)) or 0)
    assert harvest.run("t1") == 1
    (args, kw), = updates
    assert args[2] == "failed" and kw["missing"][0][2] == "auth" and "GITHUB_TOKEN" in kw["reason"]


def test_a_job_with_no_selector_fails_naming_the_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ticket = {"ticket": "t1", "slug": "s", "capture_dir": "_raw/s/d", "options": {}, "known": [], "credential_mode": "none"}
    updates = []
    monkeypatch.setattr(harvest, "open_ticket", lambda t, s=None: ticket)
    monkeypatch.setattr(harvest, "post_update", lambda *a, **k: updates.append((a, k)) or 0)
    assert harvest.run("t1") == 1
    (args, kw), = updates
    assert args[2] == "failed" and "options.select" in kw["reason"]


# ------------------------------------------------------------------ the write


def capture(tmp_path) -> Path:
    leaf = tmp_path / "_raw/s/a-one--12345678"
    leaf.mkdir(parents=True)
    (leaf / "repo.json").write_text(json.dumps(facts()))
    (leaf / "README.md").write_text("# One\n")
    (leaf / "capture.json").write_text(json.dumps({"title": "a--one", "item": "https://github.com/a/one"}))
    return leaf


def test_write_reads_a_bare_judgment_name_beside_the_capture_and_reports_the_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    leaf = capture(tmp_path)
    (leaf / "judgment.json").write_text(json.dumps(JUDGMENT))
    calls, updates = [], []
    monkeypatch.setattr(page, "open_ticket", lambda t, s=None: {"dest": "sources/github"})
    monkeypatch.setattr(page, "ops_json", lambda *a, stdin=None: calls.append(a) or (0, {"path": "sources/github/a--one.md"}))
    monkeypatch.setattr(page, "post_update", lambda *a, **k: updates.append((a, k)) or 0)
    assert page.main(["write", "_raw/s/a-one--12345678", "--ticket", "t1", "--from", "judgment.json"]) == 0
    assert calls[0][:3] == ("page", "create", "title=a--one") and "dest=sources/github" in calls[0]
    (args, kw), = updates
    assert args[1:] == ("process", "ok") and kw["written_from"] == "written.json"
    assert json.loads((leaf / "written.json").read_text()) == ["sources/github/a--one.md"]


def test_junk_on_an_unheld_repo_writes_no_page(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    leaf = capture(tmp_path)
    (leaf / "judgment.json").write_text(json.dumps({**JUDGMENT, "keep": False, "junk": "template clone"}))
    updates = []
    monkeypatch.setattr(page, "open_ticket", lambda t, s=None: {"dest": "sources/github"})
    monkeypatch.setattr(page, "ops_json", lambda *a, stdin=None: pytest.fail(f"wrote {a}"))
    monkeypatch.setattr(page, "post_update", lambda *a, **k: updates.append((a, k)) or 0)
    assert page.main(["write", "_raw/s/a-one--12345678", "--ticket", "t1", "--from", "judgment.json"]) == 0
    (args, kw), = updates
    assert args[2] == "ok" and "template clone" in kw["reason"] and "written_from" not in kw


# ------------------------------------------------------------------ the routine


def repo_page(root: Path, full: str, tags: str) -> None:
    d = root / "sources/github"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{full.replace('/', '--')}.md").write_text(
        f"---\ntype: repo\nresource: https://github.com/{full}\ntags: [{tags}]\ngh_stars: '10'\ngh_seen: 2026-10-09\n---\n")


def test_the_routine_opens_its_op_writes_each_list_into_dest_and_closes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_WIKI_ROOT", str(tmp_path))
    repo_page(tmp_path, "a/one", "github, gh-starred, mcp")
    calls = []
    monkeypatch.setattr(lists, "open_ticket", lambda t, s=None: {"dest": "research/github/lists"})
    monkeypatch.setattr(lists, "ops_json", lambda *a, stdin=None: calls.append(a) or (0, {"path": f"x/{len(calls)}.md"}))
    assert lists.main(["--only", "Stars", "ticket=t1"]) == 0
    assert calls[0] == ("op", "open", "channel-github")
    assert calls[1][:2] == ("page", "create") and "dest=research/github/lists" in calls[1] and "type=list" in calls[1]
    assert calls[-1][:4] == ("op", "close", "channel-github", "outcome=ok") and len(calls) == 3


def test_a_routines_job_with_no_dest_closes_failed_naming_the_fix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(lists, "open_ticket", lambda t, s=None: {})
    monkeypatch.setattr(lists, "ops_json", lambda *a, stdin=None: calls.append(a) or (0, {}))
    assert lists.main(["ticket=t1"]) == 1
    assert calls[-1][3] == "outcome=failed" and "dest=research/github/" in calls[-1][4]


def test_a_refused_list_page_makes_the_run_partial(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_WIKI_ROOT", str(tmp_path))
    repo_page(tmp_path, "a/one", "github, gh-starred")
    calls = []

    def ops(*a, stdin=None):
        calls.append(a)
        refused = a[:2] == ("page", "create") and "Clipped" in a[2]
        return (2, {"error": "refused"}) if refused else (0, {"path": "p.md"})

    monkeypatch.setattr(lists, "open_ticket", lambda t, s=None: {"dest": "research/github/lists"})
    monkeypatch.setattr(lists, "ops_json", ops)
    assert lists.main(["ticket=t1"]) == 0
    assert calls[-1][3] == "outcome=partial"


def test_the_routine_refuses_to_run_without_a_ticket():
    with pytest.raises(SystemExit):
        lists.main([])
