#!/usr/bin/env python3
"""The package's own check: every artifact the manifest names exists, and
every skill on disk is named; every skill's own manifest authors the three
keys a listing reads (`description`, `mode`, `argument_hint`), so the ops
CLI never fills them from the frontmatter. Exit 1 with the list otherwise.

    check-manifest.py [root]    root defaults to this checkout"""
import json, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
MODES = ("pipeline", "session")
doc = json.loads((ROOT / "llm-wiki-package.json").read_text())
problems = []
if doc.get("schema_version") != 1:
    problems.append("schema_version must be 1")
named = {(a["type"], a["name"]): a["path"] for a in doc.get("artifacts", [])}
for (kind, name), path in named.items():
    if not (ROOT / path).exists():
        problems.append(f"{kind} {name}: {path} does not exist")
    if kind == "skill" and not (ROOT / path / "SKILL.md").is_file():
        problems.append(f"skill {name}: no SKILL.md under {path}")
on_disk = {("skill", d.name) for d in (ROOT / "skills").iterdir() if (d / "SKILL.md").is_file()}
for key in sorted(on_disk - set(named)):
    problems.append(f"{key[0]} {key[1]} is on disk but not in the manifest")


def unit_problems(name: str, unit: dict) -> list:
    """The ops CLI's rules for the three keys, plus that the catalog authors all three."""
    out = []
    description, mode, hint = unit.get("description"), unit.get("mode"), unit.get("argument_hint")
    if not isinstance(description, str) or not description.strip():
        out.append("`description` must be a non-empty string")
    if not isinstance(mode, list) or not mode or not all(m in MODES for m in mode) or len(set(mode)) != len(mode):
        out.append(f"`mode` must be a non-empty list of distinct {' / '.join(MODES)}, got {mode!r}")
    elif ("pipeline" in mode) != bool(unit.get("stages")):
        # A unit with a stage is what a job can name, and that is a pipeline skill.
        out.append("`mode` holds pipeline but `stages` declares no stage" if "pipeline" in mode
                   else "`mode` lacks pipeline but `stages` declares a stage")
    if not isinstance(hint, str):
        out.append(f"`argument_hint` must be a string (\"\" for none), got {hint!r}")
    return [f"skill {name}: {p}" for p in out]


for (kind, name), path in sorted(named.items()):
    manifest = ROOT / path / "manifest.json"
    if kind == "skill" and manifest.is_file():
        problems += unit_problems(name, json.loads(manifest.read_text()))
for p in problems:
    print(p, file=sys.stderr)
print(f"{len(named)} artifacts, {len(problems)} problems")
sys.exit(1 if problems else 0)
