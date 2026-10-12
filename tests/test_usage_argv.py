"""The argv a unit's `references/usage.md` tables name is argv its scripts take.

`test_docs_cli.py` skips these: an argv cell opens with `.` or `<…>`, and
`llm-wiki-ops run` hands everything after the script path to the child
unchecked. So each script row is read here against the script's own argparse,
statically (no import, no network): every `--flag` the row names must be an
`add_argument` option in that script, and every subcommand it names must be an
`add_parser` name there. The scan is file-wide, not per parser, so it catches a
flag that does not exist, not one on the wrong subcommand.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
USAGES = sorted(ROOT.glob("skills/*/references/usage.md"))
_CELLS = re.compile(r"(?<!\\)\|")
_FLAG = re.compile(r"(?<![\w-])--[a-z][a-z-]*")
_SCRIPT = re.compile(r"^`([\w]+\.py)(?:\s+([\w-]+|--[a-z-]+))?`$")


def _argparse_of(path: Path) -> tuple[set, set]:
    """`(options, subcommands)` the script's argparse defines."""
    options, subs, has_parser, loose = set(), set(), False, False
    strings = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.add(node.value)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_argument":
                options |= {a.value for a in node.args if isinstance(a, ast.Constant) and str(a.value).startswith("--")}
            elif node.func.attr == "add_parser":
                has_parser = True
                if node.args and isinstance(node.args[0], ast.Constant):
                    subs.add(node.args[0].value)
                else:  # `add_parser(verb)` over a tuple of names: any string in the file may be one
                    loose = True
    if has_parser and loose:
        subs |= strings
    return options, subs


def _rows(usage: Path):
    """`(first cell, whole row)` of each table row of the file."""
    for line in usage.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and not line.startswith("| :--"):
            cells = [c.strip() for c in _CELLS.split(line.strip().strip("|"))]
            yield cells[0], line


def _checked(usage: Path) -> list:
    unit = usage.parents[1]
    scripts = {p.name: p for p in (unit / "scripts").glob("*.py")} if (unit / "scripts").is_dir() else {}
    sole = [p for n, p in scripts.items() if n != "to_markdown.py"]
    wrong, seen = [], 0
    for first, line in _rows(usage):
        m = _SCRIPT.match(first)
        if m:
            script, sub = scripts.get(m.group(1)), m.group(2)
            if script is None:
                wrong.append(f"{first}: no such script in {unit.name}/scripts")
                continue
        elif len(sole) == 1 and re.fullmatch(r"`[\w-]+`", first):  # the arm or subcommand of the unit's one script
            script, sub = sole[0], first.strip("`")
        else:
            continue
        seen += 1
        options, subs = _argparse_of(script)
        if sub and sub.startswith("--"):
            sub, extra = None, [sub]
        else:
            extra = []
        if sub and subs and sub not in subs:
            wrong.append(f"{first}: {script.name} has no subcommand `{sub}`")
        argv = line.split("|", 3)[-1] if m is None else line
        wrong += [f"{first}: {script.name} takes no `{f}`" for f in sorted({*_FLAG.findall(argv), *extra}) if f not in options]
    return wrong if seen else [f"{usage}: no script row was read"]


@pytest.mark.parametrize(
    "usage",
    [u for u in USAGES if (u.parents[1] / "scripts").is_dir()],
    ids=lambda p: p.parents[1].name,
)
def test_every_flag_and_subcommand_a_usage_row_names_is_in_the_script(usage):
    wrong = _checked(usage)
    assert not wrong, "\n".join(wrong)
