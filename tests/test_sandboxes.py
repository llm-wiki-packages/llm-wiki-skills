"""The stage sandboxes the package ships: each harvest or enrich stage's `sandbox_ref`
resolves to one reference here, the reference's snippet reaches a model, and
a credentialed unit can spend its credential somewhere. That the snippet's
keys are admitted is `sandboxes enable`'s to say, in test_install.py."""

from __future__ import annotations

import json
import re

import pytest

from harness import ROOT, SKILLS, SOURCE, jsonc, snippet, unit_manifest

MODEL = {"api.anthropic.com", "api.openai.com", "chatgpt.com"}
REFERENCES = ROOT / "references" / "sandboxes"

# Cookie venues, parked pending the cookie-venue measurement
# (llm-wiki-plugins#2636) and not yet moved off model hosts in their own
# snippet.
PARKED = {"circle", "substack", "teachable"}

# The stages that dispatch a slice and so may name a sandbox.
STAGES = ("harvest", "enrich")

# A unit's stage MAY carry no `sandbox_ref` at all — the ninth unit's `script`
# stage runs the seeded `harvest` sandbox instead (A-5) — so only a unit that
# DOES name one has a reference to check here.
SANDBOXED = [n for n in SKILLS if "sandbox_ref" in unit_manifest(n).get("stages", {}).get("harvest", {})]
ENRICHED = [n for n in SKILLS if "sandbox_ref" in unit_manifest(n).get("stages", {}).get("enrich", {})]
REFERENCED = [(n, stage) for n in SKILLS for stage in STAGES if "sandbox_ref" in unit_manifest(n).get("stages", {}).get(stage, {})]


def _reference(name: str, stage: str = "harvest") -> tuple[str, dict]:
    ref = unit_manifest(name)["stages"][stage]["sandbox_ref"]
    package, rel = ref.rsplit(":", 1)
    assert package == SOURCE, f"{name}: {ref} names a package other than this one"
    path = REFERENCES / f"{rel}.md"
    assert path.is_file(), f"{name}: {ref} resolves to {path.relative_to(ROOT)}, which does not exist"
    return rel, jsonc(snippet(path.read_text(encoding="utf-8")))


def _hosts(name: str) -> list[str]:
    return [k.removeprefix("host:") for k in unit_manifest(name)["keywords"] if k.startswith("host:")]


@pytest.mark.parametrize("name", SKILLS)
def test_only_harvest_and_enrich_name_a_sandbox_and_requires_names_no_network(name):
    manifest = unit_manifest(name)
    assert "network" not in manifest["requires"], name
    for stage, spec in manifest.get("stages", {}).items():
        assert stage in STAGES or "sandbox_ref" not in spec, (name, stage, spec)
        assert not {"sandbox", "reviewed"} & set(spec), f"{name}: a package manifest carries no binding"


@pytest.mark.parametrize("name", SANDBOXED)
def test_the_reference_is_the_units_venue_and_its_snippet_is_one_policy(name):
    rel, doc = _reference(name)
    venue = unit_manifest(name)["venue"]
    assert rel == f"{venue}/{venue}.harvest", rel
    assert set(doc) == {"v", "profile"} and doc["v"] == 1, doc
    allow = doc["profile"]["network"]["allow_domain"]
    if venue in PARKED:
        assert MODEL <= set(allow), f"{name}: the snippet lacks a model endpoint"
    else:
        assert not MODEL & set(allow), f"{name}: the snippet still names a model endpoint; the harness profile supplies it"


@pytest.mark.parametrize("name", [n for n in SKILLS if unit_manifest(n)["requires"].get("credential")])
def test_a_credentialed_unit_claims_an_exact_host_its_snippet_reaches(name):
    stage = "harvest" if name in SANDBOXED else "enrich"
    _, doc = _reference(name, stage)
    claims = [h for h in _hosts(name) if not h.startswith("*")]
    assert set(claims) & set(doc["profile"]["network"]["allow_domain"]), f"{name}: no exact host: claim is reached, so dispatch refuses a job with no host"


@pytest.mark.parametrize("name", ENRICHED)
def test_an_enrich_reference_is_the_units_venue_and_its_snippet_is_one_policy(name):
    rel, doc = _reference(name, "enrich")
    assert rel == f"{unit_manifest(name)['venue']}/{unit_manifest(name)['venue']}.enrich", rel
    assert set(doc) == {"v", "profile"} and doc["v"] == 1, doc
    allow = doc["profile"]["network"]["allow_domain"]
    assert allow and not MODEL & set(allow), f"{name}: an enrich snippet names its venue's hosts, never a model endpoint"


def test_two_units_of_one_venue_never_share_a_stage_sandbox_name():
    """`skills install` names the wiki sandbox `<venue>-<stage>`, and refuses to
    overwrite one a different reference wrote: two units of one venue and stage
    cannot both be installed in one wiki."""
    names = [f"{unit_manifest(n)['venue']}-{stage}" for n, stage in REFERENCED]
    assert len(names) == len(set(names)), sorted(n for n in names if names.count(n) > 1)


def _section_json(text: str, heading: str):
    """The one fenced `json` block under `## <heading>`, parsed, or None when there is no such section."""
    match = re.search(rf"^## {heading}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        return None
    fences = re.findall(r"^```json\n(.*?)^```$", match.group(1), re.M | re.S)
    assert len(fences) == 1, f"## {heading} carries {len(fences)} json blocks, not one"
    return json.loads(fences[0])


def _strings(value):
    """Every string leaf, but a route's `endpoint_rules`: URL paths, not machine paths."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, one in value.items():
            if key != "endpoint_rules":
                yield from _strings(one)
    elif isinstance(value, list):
        for one in value:
            yield from _strings(one)


@pytest.mark.parametrize("name", SANDBOXED)
def test_machine_and_probe_name_bins_by_placeholder_never_by_path(name):
    rel, _ = _reference(name)
    text = (REFERENCES / f"{rel}.md").read_text(encoding="utf-8")
    machine, probe = _section_json(text, "Machine"), _section_json(text, "Probe")
    if machine is None and probe is None:
        return
    bins = {b["bin"] for b in unit_manifest(name)["requires"].get("bins", [])}
    # A probe runs one of the unit's bins: a machine block comes with one
    # exactly where the unit declares a bin to run it with.
    assert machine is not None, f"{name}: a probe with no machine block probes nothing"
    assert (probe is not None) == bool(bins), f"{name}: a machine block and its probe come together where the unit has bins"
    for value in [*_strings(machine), *(probe or [])]:
        assert not value.startswith(("/", "~")), f"{name}: {value!r} is a machine path"
        for placeholder in re.findall(r"\{bin:([^}]*)\}", value):
            assert placeholder in bins, f"{name}: {{bin:{placeholder}}} is not in requires.bins"
    if probe is not None:
        assert isinstance(probe, list) and probe and all(isinstance(a, str) for a in probe), probe
        assert probe[0].startswith("{bin:"), probe


def test_every_reference_is_one_a_unit_names():
    named = {_reference(n, stage)[0] for n, stage in REFERENCED}
    shipped = {str(p.relative_to(REFERENCES).with_suffix("")) for p in REFERENCES.rglob("*.md")}
    assert shipped == named, shipped ^ named


def test_the_snippet_reader_skips_comments_and_keeps_urls():
    assert jsonc('{"a": "https://x.example/y", // gone\n "b": 1}') == {"a": "https://x.example/y", "b": 1}
    assert re.fullmatch(r"\{\n\}\n", snippet("x\n```jsonc\n{\n}\n```\n"))
