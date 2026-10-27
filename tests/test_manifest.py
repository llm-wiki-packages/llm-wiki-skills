"""The manifest agrees with the tree, and every unit's own manifest carries
the keys the package rail needs."""

from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from harness import MANIFEST, ROOT, SKILLS, unit_manifest

_FLOOR = re.compile(r"^>=\d+\.\d+(\.\d+)?$")


def test_check_manifest_passes_on_the_tree():
    cp = subprocess.run([sys.executable, str(ROOT / "scripts" / "check-manifest.py")], capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr


@pytest.mark.parametrize(
    ("edit", "said"),
    [
        (lambda m: m.pop("description"), "`description` must be a non-empty string"),
        (lambda m: m.update(description=" "), "`description` must be a non-empty string"),
        (lambda m: m.pop("mode"), "`mode` must be a non-empty list"),
        (lambda m: m.update(mode=[]), "`mode` must be a non-empty list"),
        (lambda m: m.update(mode=["pipeline", "pipeline"]), "`mode` must be a non-empty list"),
        (lambda m: m.update(mode=["cron"]), "`mode` must be a non-empty list"),
        (lambda m: m.update(mode=["session"]), "`mode` lacks pipeline but `stages` declares a stage"),
        (lambda m: m.update(stages={}), "`mode` holds pipeline but `stages` declares no stage"),
        (lambda m: m.pop("argument_hint"), "`argument_hint` must be a string"),
    ],
)
def test_check_manifest_refuses_a_unit_that_does_not_author_the_listing_keys(tmp_path, edit, said):
    """The catalog authors all three, so `skills install` never fills one from
    the frontmatter, and holds them to the ops CLI's own rules."""
    (tmp_path / "llm-wiki-package.json").write_text((ROOT / "llm-wiki-package.json").read_text())
    for name in SKILLS:
        unit = tmp_path / "skills" / name
        unit.mkdir(parents=True)
        (unit / "SKILL.md").write_text("")
        manifest = unit_manifest(name)
        if name == "channel-youtube":
            edit(manifest)
        (unit / "manifest.json").write_text(json.dumps(manifest))
    cp = subprocess.run([sys.executable, str(ROOT / "scripts" / "check-manifest.py"), str(tmp_path)], capture_output=True, text=True)
    assert cp.returncode == 1 and f"skill channel-youtube: {said}" in cp.stderr, cp.stderr
    assert cp.stderr.count("\n") == 1, cp.stderr


# The units a session runs: some stage of each carries no `script`, so an
# agent follows its body, and the body spells ops verbs of the version it pins.
SESSION_UNITS = [n for n in SKILLS if any("script" not in s for s in unit_manifest(n).get("stages", {}).values())]


def test_the_session_unit_selection_is_not_empty():
    """An empty parametrize skips; this fails, so the selection cannot drift to nothing unseen."""
    assert SESSION_UNITS, "no unit declares a stage a session runs"


@pytest.mark.parametrize("name", SESSION_UNITS)
def test_every_session_unit_declares_its_ops_floor(name):
    floor = (unit_manifest(name).get("requires") or {}).get("ops")
    assert isinstance(floor, str) and _FLOOR.match(floor), f"{name}: requires.ops is {floor!r}"


def test_min_ops_version_is_a_bare_version():
    assert re.match(r"^\d+\.\d+\.\d+$", MANIFEST["min_ops_version"])


def _version(text: str) -> tuple:
    return tuple(int(b) for b in text.removeprefix(">=").split("."))


@pytest.mark.parametrize("name", SKILLS)
def test_every_units_floor_is_at_or_above_the_packages(name):
    """`test_either_step_of_a_unit_opens_with_the_policy_read` pins this for
    the eight channel units, from their own `## Stages` intro; a `script`
    unit like `web-page` opens neither step with a policy read, so nothing
    else checks its floor. A unit spelling a lower `requires.ops` would claim
    to run on an ops CLI that `check-manifest.py` never rejects it for."""
    floor = unit_manifest(name)["requires"].get("ops")
    assert floor, f"{name}: declares no requires.ops"
    assert _version(floor) >= _version(MANIFEST["min_ops_version"]), f"{name}: requires.ops {floor} is under the package's min_ops_version"
