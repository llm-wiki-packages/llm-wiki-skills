"""channel-github's catalog against fixture pages — never the CLI."""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
spec = importlib.util.spec_from_file_location("gh_catalog", HERE.parent / "scripts" / "catalog.py")
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)

TODAY = "2026-10-09"
W = dict(catalog.DEFAULT_WEIGHTS)


def page_text(full, stars, tags, **kw):
    lines = ["---", "type: " + kw.get("type", "repo"), f'title: "{full.replace("/", "--")}"',
             f"resource: https://github.com/{full}", f'description: "{kw.get("desc", "Does things.")}"']
    if kw.get("block_tags"):
        lines.append("tags:")
        lines += [f"  - {t}" for t in tags]
    else:
        lines.append(f"tags: [{', '.join(tags)}]")
    if stars is not None:
        lines.append(f"gh_stars: '{stars}'")
        lines.append(f"gh_seen: {kw.get('seen', TODAY)}")
    for k in ("gh_stars_prev", "gh_stars_prev_at", "gh_first_seen", "gh_starred_at", "gh_pushed", "gh_via", "gh_topics"):
        if k in kw:
            lines.append(f"{k}: {kw[k]}")
    lines += ["harvested:", "  at: 2026-10-09T00:00:00Z", "---", "", "> [!summary]", "> " + kw.get("summary", "Summary here."), "",
              "## What it's for", "", "- " + kw.get("use", "a job"), "", "## Notes", ""]
    return "\n".join(lines) + "\n"


def wiki(tmp_path):
    (tmp_path / ".llm-wiki.toml").write_text("")
    d = tmp_path / "sources/github"
    d.mkdir(parents=True)
    (d / "a--skills.md").write_text(page_text("a/skills", 20000, ["github", "gh-starred", "agent-skills", "marketing"],
                                              gh_starred_at="2026-01-01", gh_via="stars:me", use="write ad copy",
                                              gh_stars_prev=15000, gh_stars_prev_at="2026-09-01", gh_first_seen="2026-01-02"))
    (d / "b--seo.md").write_text(page_text("b/seo", 300, ["github", "gh-clipped", "marketing"], block_tags=True, gh_first_seen="2026-10-01"))
    (d / "c--big.md").write_text(page_text("c/big", 90000, ["github", "gh-watched", "agent-frameworks"], gh_via="org:c", gh_pushed="2026-10-01"))
    (d / "GitHub list — Stars.md").write_text("---\ntype: list\n---\n")
    clips = tmp_path / "sources/clips"
    clips.mkdir(parents=True)
    (clips / "old clip.md").write_text("---\ntype: clip\nresource: https://github.com/d/legacy\ntags: [clip]\n---\n")
    (clips / "dupe.md").write_text("---\ntype: clip\nresource: https://github.com/b/seo\n---\n")
    return tmp_path


def test_frontmatter_flow_block_nested_and_quotes():
    fm, body = catalog.parse_frontmatter("---\na: 'it''s'\nb: [x, \"y\"]\nc:\n  - p\n  - q\nd:\n  at: 1\ne: ~\n---\nBODY\n")
    assert fm == {"a": "it's", "b": ["x", "y"], "c": ["p", "q"], "d": True, "e": ""}
    assert body == "BODY\n"


def test_as_int_reads_clipper_counts():
    assert catalog.as_int("12,345") == 12345 and catalog.as_int("1.2k") == 1200 and catalog.as_int("") is None


def test_catalog_dedupes_repos_first_and_skips_lists(tmp_path):
    root = wiki(tmp_path)
    recs = {r["repo"]: r for r in catalog.load_catalog(root, "sources/github", ("sources/clips",))}
    assert set(recs) == {"a/skills", "b/seo", "c/big", "d/legacy"}
    assert recs["b/seo"]["path"] == "sources/github/b--seo.md"
    assert recs["b/seo"]["clipped"] and recs["b/seo"]["categories"] == ["marketing"]
    assert recs["a/skills"]["starred"] and recs["a/skills"]["use_for"] == ["write ad copy"]
    assert recs["c/big"]["watched"] and not recs["c/big"]["starred"]
    assert recs["d/legacy"]["stars"] is None


def test_rank_by_tags_and_text(tmp_path):
    recs = catalog.load_catalog(wiki(tmp_path), "sources/github", ("sources/clips",))
    rows = catalog.ranked(recs, {"tags_all": ["marketing"]}, "score", 0, W, TODAY)
    assert [r["repo"] for r in rows] == ["a/skills", "b/seo"]
    rows = catalog.ranked(recs, {"text": "agent skills marketing"}, "score", 0, W, TODAY)
    assert rows[0]["repo"] == "a/skills"
    assert [r["repo"] for r in catalog.ranked(recs, {}, "stars", 1, W, TODAY)] == ["c/big"]


def test_starred_outranks_bigger_unstarred_by_default(tmp_path):
    recs = catalog.load_catalog(wiki(tmp_path), "sources/github", ("sources/clips",))
    a = next(r for r in recs if r["repo"] == "a/skills")
    c = next(r for r in recs if r["repo"] == "c/big")
    assert catalog.score(a, W, TODAY) > catalog.score(c, W, TODAY)


def test_lists_build_whats_new_and_categories(tmp_path):
    recs = catalog.load_catalog(wiki(tmp_path), "sources/github", ("sources/clips",))
    cfg = {"weights": W, "lists": [{"name": "What's new", "kind": "whats-new", "title": "GitHub list — What's new", "window_days": 30, "format": "table"},
                                   {"name": "Stars", "title": "GitHub list — Stars", "filter": {"starred": True}, "sort": "starred"}],
           "by_category": {"enabled": True, "min": 2, "title": "GitHub list — {category}"}}
    built = {t: b for t, _, b in catalog.build_lists(cfg, recs, TODAY)}
    new = built["GitHub list — What's new"]
    jumped, fresh = new.split("## New to the wiki")
    assert "a--skills" in jumped and "+5.0k" in jumped
    assert "b--seo" in fresh and "a--skills" not in fresh
    assert "[[a--skills|a/skills]]" in built["GitHub list — Stars"] and "c--big" not in built["GitHub list — Stars"]
    assert set(built) == {"GitHub list — What's new", "GitHub list — Stars", "GitHub list — marketing"}


def test_table_escapes_pipes():
    rec = {"page": "a--b", "repo": "a/b", "description": "x | y", "stars": 5, "language": "", "pushed": None,
           "starred": False, "clipped": True, "watched": False, "stars_prev": None}
    row = catalog.render_rows([rec], "table").splitlines()[-1]
    assert "x \\| y" in row and "[[a--b\\|a/b]]" in row


def test_frontmatter_unindented_block_list():
    fm, _ = catalog.parse_frontmatter("---\ntags:\n- github\n- marketing\nresource: x\n---\n")
    assert fm == {"tags": ["github", "marketing"], "resource": "x"}


def test_paths_from_search_json(tmp_path):
    f = tmp_path / "hits.json"
    f.write_text(json.dumps({"hits": [{"locator": "sources/github/a--skills.md", "source_path": "sources/github/a--skills.md"}]}))
    assert catalog.read_paths(str(f)) == {"sources/github/a--skills.md"}


def test_shipped_config_and_clipper_template_parse():
    refs = HERE.parent / "references"
    cfg = json.loads((refs / "lists.json").read_text())
    assert cfg["repos"] == "sources/github" and all(l.get("sort", "score") in catalog.SORTS for l in cfg["lists"])
    clip = json.loads((refs / "clipper-github-repo.json").read_text())
    assert clip["path"] == "sources/github"
    names = {p["name"] for p in clip["properties"]}
    assert {"type", "resource", "tags", "gh_stars", "status"} <= names


def test_scan_records_carry_the_signal_tags_a_retag_keeps(tmp_path):
    recs = {r["repo"]: r for r in catalog.load_catalog(wiki(tmp_path), "sources/github", ("sources/clips",))}
    assert recs["a/skills"]["signals"] == ["github", "gh-starred"] and recs["a/skills"]["categories"] == ["agent-skills", "marketing"]


def test_the_root_is_the_runs_own_never_a_search_for_the_wiki_file(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_WIKI_ROOT", str(tmp_path))
    assert catalog.wiki_root() == tmp_path
    monkeypatch.delenv("LLM_WIKI_ROOT")
    monkeypatch.chdir(tmp_path)
    assert catalog.wiki_root() == tmp_path
