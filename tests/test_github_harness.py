"""channel-github, the harness tier: the unit installed and enabled
through the REAL CLI, its two script stages started by the runner in the jails
its `sandbox.jsonc` composes. Nothing here reaches GitHub: the harvest case is the
one that fails before its first call, and the routine reads only pages the
case wrote.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import time

from harness import declared_job, enabled, no_jail_here, plugin_refused, rooted, run, shown

UNIT = "channel-github"
TODAY = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
REPOS = "sources/github"


def _ran(ops, env, wiki, slug: str) -> dict:
    """The job claimed and its one clock-stage ticket run to its landing; the ticket's record."""
    r = run(ops, rooted(env, wiki), "--json", "jobs", "claim", slug)
    assert r.returncode == 0, r.stdout + r.stderr
    mine = [c for c in r.data["claimed"] if c["slug"] == slug]
    assert mine and mine[0]["tickets"], f"{slug}: claim minted no ticket: {r.stdout}"
    ticket_id = mine[0]["tickets"][0]["id"]
    r = run(ops, rooted(env, wiki), "--json", "tickets", "run", ticket_id, "wait=120s")
    no_jail_here(r)
    assert r.returncode == 0, r.stdout + r.stderr
    waited = r.data.get("wait") or {}
    assert waited.get("event") == "exit", r.stdout
    path = waited["table"][0].get("log")
    log = ""
    if path:
        with open(path, encoding="utf-8", errors="replace") as f:
            log = f.read()
        plugin_refused(wiki, log)
    # `wait=` answers at the worker's exit; the pass that exit runs lands the ticket a moment later.
    deadline = time.monotonic() + 60
    while shown(ops, env, wiki, ticket_id)["state"] == "active":
        assert time.monotonic() < deadline, f"{ticket_id}: still active 60s after its worker exited"
        time.sleep(0.5)
    return {"id": ticket_id, "update": waited["table"][0].get("update"), "log": log}


def test_two_harvest_jobs_share_the_one_repo_dest(ops, env, wiki):
    """Every github harvest job lands in `sources/github`, so a repo is one page however many jobs name it."""
    first = declared_job(ops, env, wiki, UNIT, "harness-github-stars", "options.select=stars:octocat", f"dest={REPOS}", slug="harness-github-stars")
    second = declared_job(ops, env, wiki, UNIT, "harness-github-watch", "options.select=org:example-org", f"dest={REPOS}", slug="harness-github-watch")
    assert first.dest == second.dest == REPOS
    assert first.record["harvest"]["skill"] == first.record["process"]["skill"] == UNIT


def test_the_harvest_script_runs_in_its_jail_and_fails_a_bad_selector_by_name(ops, env, wiki):
    """The runner starts `harvest.py` with `ticket=<id>`; it opens and updates its own ticket from inside the jail."""
    job = declared_job(ops, env, wiki, UNIT, "harness-github-bad", "options.select=nope:x", f"dest={REPOS}", slug="harness-github-bad")
    ran = _ran(ops, env, wiki, job.slug)
    record = shown(ops, env, wiki, ran["id"])
    said = json.dumps(ran["update"]) + ran["log"][-2500:] + json.dumps(record)
    assert "nope:x" in said, said[:1500]
    assert ran["update"] and ran["update"]["status"] == "failed", said[:1500]


def _repo_page(ops, env, wiki, full: str, tags: str, stars: int) -> str:
    owner, name = full.split("/")
    r = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={owner}--{name}", f"dest={REPOS}", "type=repo",
            f"tags={tags}", f"resource=https://github.com/{full}", f"gh_stars={stars}", f"gh_seen={TODAY}",
            f"gh_first_seen={TODAY}", "description=A harness repo.", "--stdin", input="> [!summary]\n> A harness repo.\n")
    assert r.returncode == 0, r.stdout + r.stderr
    return r.data["path"]


def test_the_routine_regenerates_the_list_pages_into_its_dest_under_its_op(ops, env, wiki):
    """A routines job naming the unit runs `lists.py` in the routine stage's jail: it reads `sources/`, writes only its `dest`, and its op close is the report."""
    enabled(ops, env, wiki, UNIT)
    paths = [_repo_page(ops, env, wiki, "example-org/agent-kit", "github,gh-starred,agent-skills", 1200),
             _repo_page(ops, env, wiki, "example-org/mcp-db", "github,gh-watched,agent-skills", 40)]
    r = run(ops, rooted(env, wiki), "--json", "git", "commit", *paths, "message=harness: repo pages the routine lists")
    assert r.returncode == 0, r.stdout + r.stderr
    dest = "research/github/harness-github-lists"
    r = run(ops, rooted(env, wiki), "--json", "jobs", "add", "harness-github-lists", f"routines={UNIT}", f"dest={dest}", "every=once",
            "description=harness: the list routine")
    assert r.returncode == 0, r.stdout + r.stderr
    ran = _ran(ops, env, wiki, "harness-github-lists")
    record = shown(ops, env, wiki, ran["id"])
    assert record["state"] == "done", ran["log"][-2500:] + json.dumps(record)[:800]
    written = sorted(p.name for p in (wiki / dest).glob("*.md"))
    assert "GitHub list — Stars.md" in written and "GitHub list — agent-skills.md" not in written, written  # by_category needs 3
    stars = (wiki / dest / "GitHub list — Stars.md").read_text(encoding="utf-8")
    assert "type: list" in stars and "[[example-org--agent-kit|example-org/agent-kit]]" in stars and "mcp-db" not in stars, stars[:1200]
    assert ran["update"]["status"] == "ok" and set(ran["update"]["written"]) >= {f"{dest}/GitHub list — Stars.md"}, ran["update"]
    latest = run(ops, rooted(env, wiki), "--json", "op", "latest", UNIT, "filter=outcome:ok")
    assert latest.returncode == 0 and latest.data["found"] is True, latest.stdout + latest.stderr
    subject = subprocess.run(["git", "-C", str(wiki), "log", "-1", "--format=%B", "--", f"{dest}/GitHub list — Stars.md"],
                             capture_output=True, text=True, check=True).stdout
    assert f"Op: {UNIT}" in subject, subject
