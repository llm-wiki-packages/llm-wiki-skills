"""The sandboxes the package ships: each unit's unit-level `sandbox_ref` resolves
to one template here, the template names no model host, its stages are the
manifest's dispatched stages plus `routine`, and a credentialed unit can spend
its credential somewhere. That the ops package's v2 reader accepts every
template is read through the installed package, and that install writes and
validates it is `skills install`'s to say."""

from __future__ import annotations

import json
import re
import subprocess

import pytest

from harness import ROOT, SKILLS, SOURCE, TEMPLATES, _cli_python, installed_sandbox, jsonc, rooted, run, template, template_name, unit_manifest

MODEL = {"api.anthropic.com", "api.openai.com", "chatgpt.com"}

# The stage a unit's sandbox always carries beside the manifest's own: the
# jail of `llm-wiki-ops run <unit> scripts/x.py`.
ALWAYS = "routine"


def _dispatched(name: str) -> set:
    return {*unit_manifest(name).get("stages", {}), ALWAYS}


def _hosts(name: str) -> list[str]:
    return [k.removeprefix("host:") for k in unit_manifest(name)["keywords"] if k.startswith("host:")]


def _network(name: str) -> dict:
    return template(template_name(name))["stages"].get("harvest", {}).get("network", {})


@pytest.mark.parametrize("name", SKILLS)
def test_a_unit_names_one_template_at_the_unit_level_and_no_stage_or_venue_does(name):
    manifest = unit_manifest(name)
    assert "network" not in manifest["requires"], name
    assert "venue" not in manifest, f"{name}: `venue` is gone; the template name is the unit's sandbox_ref"
    for stage, spec in manifest.get("stages", {}).items():
        assert not {"sandbox", "reviewed", "sandbox_ref"} & set(spec), f"{name}.{stage}: a package manifest carries no binding, and sandbox_ref is unit-level"
    assert (TEMPLATES / f"{template_name(name)}.jsonc").is_file(), f"{name}: sandbox_ref resolves to no template"
    assert (TEMPLATES / f"{template_name(name)}.md").is_file(), f"{name}: sandbox_ref resolves to no help prose"


def test_every_template_is_one_a_unit_names():
    named = {template_name(n) for n in SKILLS}
    shipped = {p.stem for p in TEMPLATES.iterdir()}
    assert shipped == named, shipped ^ named
    assert {p.suffix for p in TEMPLATES.iterdir()} == {".jsonc", ".md"}
    assert len(named) == len(SKILLS) == 13, (len(named), len(SKILLS))


@pytest.mark.parametrize("name", SKILLS)
def test_the_template_is_a_skill_sandbox_whose_stages_are_the_manifests_plus_routine(name):
    doc = template(template_name(name))
    assert set(doc) == {"v", "kind", "stages"} and doc["v"] == 2 and doc["kind"] == "skill", sorted(doc)
    assert set(doc["stages"]) == _dispatched(name), (set(doc["stages"]), _dispatched(name))
    for stage, body in doc["stages"].items():
        assert body["extends"] == stage, (name, stage)


@pytest.mark.parametrize("name", SKILLS)
def test_no_template_names_a_model_endpoint(name):
    for stage, body in template(template_name(name))["stages"].items():
        allow = set(body.get("network", {}).get("allow_domain", []))
        assert not MODEL & allow, f"{name}.{stage}: names a model endpoint; the harness profile supplies it"


# What each template's stages reach beyond the stock bases, explicitly: a grant
# dropped or added shows here. Hosts are the harvest stage's `allow_domain`;
# no other stage names a host.
HOSTS = {
    "circle": ["circle.so", "*.circle.so"],
    "daily-report": [],
    "frameio": ["frame.io", "*.frame.io"],
    "github": ["api.github.com"],
    "gmail": ["gmailmcp.googleapis.com"],
    "gmail-gws": ["gmail.googleapis.com", "oauth2.googleapis.com", "www.googleapis.com"],
    "hubspot-cms": ["play.hubspotvideo.com", "image.mux.com", "stream.mux.com", "*.mux.com"],
    "notion": ["api.notion.com"],
    "parentsquare": ["www.parentsquare.com"],
    "spotify": ["spotify.com", "*.spotify.com", "*.scdn.co", "*.spotifycdn.com", "itunes.apple.com"],
    "substack": ["substack.com", "*.substack.com", "substackcdn.com"],
    "web-page": [],
    "youtube": ["youtube.com", "*.youtube.com", "youtu.be", "*.googlevideo.com", "*.ytimg.com"],
}

# `(template, stage) -> machine_reads tokens`; absent means none.
MACHINE_READS = {
    ("circle", "harvest"): ["playwright-cache"],
    ("frameio", "harvest"): ["playwright-cache"],
    ("hubspot-cms", "harvest"): ["playwright-cache"],
    ("substack", "harvest"): ["playwright-cache"],
    ("youtube", "harvest"): ["yt-dlp-cache"],
}

# `(template, stage) -> filesystem`; absent means none.
FILESYSTEM = {
    ("daily-report", "routine"): {
        "read": ["$WORKDIR/.git", "$WORKDIR/research", "$WORKDIR/sources"],
        "allow": ["$WORKDIR/wiki"],
    },
    ("github", "routine"): {"read": ["$WORKDIR/sources"]},
}


def test_the_expected_tables_name_exactly_the_shipped_templates():
    assert set(HOSTS) == {template_name(n) for n in SKILLS}
    stages = {(template_name(n), s) for n in SKILLS for s in template(template_name(n))["stages"]}
    assert set(MACHINE_READS) <= stages and set(FILESYSTEM) <= stages


@pytest.mark.parametrize("name", SKILLS)
def test_a_template_reaches_exactly_the_hosts_it_is_expected_to(name):
    tname = template_name(name)
    for stage, body in template(tname)["stages"].items():
        hosts = body.get("network", {}).get("allow_domain", [])
        assert hosts == (HOSTS[tname] if stage == "harvest" else []), f"{tname}.{stage}: hosts {hosts}"
    if HOSTS[tname]:
        assert HOSTS[tname] == _network(name)["allow_domain"], f"{tname}: harvest lost its network block"


@pytest.mark.parametrize("name", SKILLS)
def test_a_template_grants_exactly_the_machine_reads_and_filesystem_it_is_expected_to(name):
    tname = template_name(name)
    for stage, body in template(tname)["stages"].items():
        assert body.get("machine_reads", []) == MACHINE_READS.get((tname, stage), []), f"{tname}.{stage}: machine_reads"
        assert body.get("filesystem", {}) == FILESYSTEM.get((tname, stage), {}), f"{tname}.{stage}: filesystem"


# What a unit spends: a binding name of a route, a payload file, a granted directory.
CREDENTIAL_KEYS = ("credentials",)


@pytest.mark.parametrize("name", [n for n in SKILLS if any(unit_manifest(n)["requires"].get(k) for k in CREDENTIAL_KEYS)])
def test_a_credentialed_unit_claims_an_exact_host_its_harvest_stage_reaches(name):
    claims = [h for h in _hosts(name) if not h.startswith("*")]
    assert set(claims) & set(_network(name).get("allow_domain", [])), f"{name}: no exact host: claim is reached, so dispatch refuses a job with no host"


@pytest.mark.parametrize("name", SKILLS)
def test_a_route_is_named_by_the_stage_and_the_manifest_declares_its_binding(name):
    network = _network(name)
    routes = network.get("credentials", [])
    assert sorted(routes) == sorted(network.get("custom_credentials", {})), f"{name}: a route name pairs with its custom_credentials body"
    declared = unit_manifest(name)["requires"].get("credentials", {}).get("routes", {})
    if name == "channel-spotify":  # the binding is undeclared, which reads "optional"
        assert not declared and routes == ["spotify"], (declared, routes)
    else:
        assert sorted(declared) == sorted(routes), f"{name}: requires.credentials.routes {sorted(declared)} vs the template's {sorted(routes)}"
    for route, body in network.get("custom_credentials", {}).items():
        assert set(body) <= {"upstream", "env_var", "credential_format", "endpoint_rules"}, (name, route, sorted(body))
        assert body["upstream"].startswith("https://") and body["credential_format"].count("{}") == 1, (name, route, body)


@pytest.mark.parametrize("name", SKILLS)
def test_a_probe_names_bins_by_placeholder_never_by_path(name):
    bins = {b["bin"] for b in unit_manifest(name)["requires"].get("bins", [])}
    for stage, body in template(template_name(name))["stages"].items():
        for argv in body.get("probe", []):
            assert isinstance(argv, list) and argv and all(isinstance(a, str) for a in argv), (name, stage, argv)
            assert argv[0].startswith("{bin:"), f"{name}.{stage}: a probe runs one of the unit's bins by placeholder: {argv}"
            for value in argv:
                assert not value.startswith(("/", "~")), f"{name}: {value!r} is a machine path"
                for placeholder in re.findall(r"\{bin:([^}]*)\}", value):
                    assert placeholder in bins, f"{name}: {{bin:{placeholder}}} is not in requires.bins"


@pytest.mark.parametrize("name", SKILLS)
def test_every_mcp_server_is_a_bin_the_unit_declares(name):
    """Install's unit rule, held here so a template edit fails before a wiki sees it."""
    bins = {b["bin"] for b in unit_manifest(name)["requires"].get("bins", [])}
    for stage, body in template(template_name(name))["stages"].items():
        for server in body.get("mcp", []):
            assert server["command"] in bins, f"{name}.{stage}: mcp names {server['command']!r}, which requires.bins does not declare"
            assert "script" not in unit_manifest(name)["stages"][stage], f"{name}: a script stage runs no harness, so its template carries no mcp"


def test_the_mcp_reader_finds_the_one_unit_that_declares_a_server():
    """An arm that parametrizes over nothing passes quietly: the template this one exists for is the known member."""
    declaring = [n for n in SKILLS if any(body.get("mcp") for body in template(template_name(n))["stages"].values())]
    assert declaring == ["channel-parentsquare"], declaring


def test_no_template_names_a_machine_path():
    """A machine path reaches a stage only by a `machine_reads` token, never as an entry."""
    for name in SKILLS:
        for stage, body in template(template_name(name))["stages"].items():
            for axis, entries in (body.get("filesystem") or {}).items():
                for entry in entries:
                    assert entry.startswith("$WORKDIR/"), f"{name}.{stage}.filesystem.{axis}: {entry!r}"


def test_the_template_reader_skips_comments_and_keeps_urls():
    assert jsonc('{"a": "https://x.example/y", // gone\n "b": 1}') == {"a": "https://x.example/y", "b": 1}


_READ = """
import json, sys
from pathlib import Path
from llm_wiki_ops.lib.errors import Refused
from llm_wiki_ops.lib.sandboxes import v2

found = {}
for path in sorted(Path(sys.argv[1]).glob("*.jsonc")):
    try:
        read = v2.read(path)
        found[path.stem] = {"kind": read.document["kind"], "stages": sorted(read.stages), "refused": None}
    except Refused as exc:
        found[path.stem] = {"kind": None, "stages": [], "refused": str(exc)}
print(json.dumps(found))
"""


def test_the_ops_package_reads_every_template_with_the_v2_reader(ops):
    """`v2.read` through the interpreter the installed ops package runs under: a refusal here is a template that `skills install` would refuse."""
    done = subprocess.run([*_cli_python(ops), "-c", _READ, str(TEMPLATES)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    found = json.loads(done.stdout.strip().splitlines()[-1])
    assert len(found) == len(SKILLS), sorted(found)
    assert {n: one["refused"] for n, one in found.items() if one["refused"]} == {}
    assert {one["kind"] for one in found.values()} == {"skill"}
    for name in SKILLS:
        assert found[template_name(name)]["stages"] == sorted(_dispatched(name)), name


@pytest.mark.parametrize("name", SKILLS)
def test_install_writes_the_units_sandbox_and_validates_it(ops, env, wiki, name):
    """Install's validation is the check: the template's stages equal the manifest's plus `routine`, and the written file records where it came from."""
    r = run(ops, rooted(env, wiki), "--json", "skills", "install", name)
    assert r.returncode == 0, r.stdout + r.stderr
    written = installed_sandbox(ops, env, wiki, name)
    assert written["kind"] == "skill" and set(written["stages"]) == _dispatched(name), written
    assert written["source"]["ref"] == f"{SOURCE}:{template_name(name)}", written["source"]
    assert {"template", "written"} <= set(written["source"]), written["source"]
    assert all(body["extends"] == stage for stage, body in written["stages"].items()), written["stages"]


def test_the_references_tree_the_templates_replaced_is_gone():
    assert TEMPLATES.is_dir() and not (ROOT / "references").exists()
