"""What the daily-report skill's body claims about its own directory."""
import json
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1]
BODY = (SKILL / "SKILL.md").read_text(encoding="utf-8")
SETUP = SKILL / "references" / "setup.md"


def test_the_frontmatter_names_this_directory():
    assert BODY.startswith("---\n")
    front = BODY.split("---\n", 2)[1]
    assert f"name: {SKILL.name}\n" in front
    assert "description:" in front


def test_the_body_names_itself_as_a_unit_invocation():
    assert "whereami skill=daily-report " in BODY
    assert "llm-wiki:daily-report" not in BODY


LOCAL = sorted(p.name for p in (SKILL / "references").glob("*"))


@pytest.mark.parametrize("local", [n for n in LOCAL if n not in {"enable.md", "customize.md"}])
def test_every_skill_local_reference_it_ships_is_named_in_the_body(local):
    assert local in BODY


def test_the_skill_ships_local_references_to_check():
    assert len(LOCAL) >= 2, LOCAL


# `setup` is a recurring argument, so an unconditional retire refuses on a
# re-run ("carries no 'daily-report-setup' overlay") between the overlay saved
# and the commit that would have kept it.
MARKER_GUARD = "when §1's read returned it"


def test_the_setup_marker_is_retired_only_when_it_was_found():
    setup = SETUP.read_text(encoding="utf-8")
    assert "llm-wiki-ops policy retire daily-report-setup" in setup
    assert MARKER_GUARD in setup, "setup.md retires the marker unconditionally"
    assert MARKER_GUARD in BODY, "the skill body's §8 clause carries no condition"


# The `ops-morning` job runs this unit as `/daily-report ticket=<id>
# stage=routine`; the claim gate admits that job only where the enabled
# manifest serves `routine`.
MANIFEST = json.loads((SKILL / "manifest.json").read_text(encoding="utf-8"))
ROUTINE = BODY.split("\n## 10. ", 1)[1].split("\n## ", 1)[0] if "\n## 10. " in BODY else ""


def test_the_manifest_serves_the_routine_stage_in_its_own_sandbox():
    assert MANIFEST["kind"] != "tool", "a tool unit serves no stage, so no job can run it"
    routine = MANIFEST["stages"]["routine"]
    assert routine["sandbox_ref"].endswith(":daily-report/daily-report.routine"), routine


def test_a_scheduled_run_checks_its_ticket_is_a_routine():
    scope = BODY.split("\n## 1. ", 1)[0]
    assert "ticket=<id> stage=routine" in scope, "the scope names no scheduled entry"
    assert "tickets open <id>" in scope and "`stage` must be `routine`" in scope


def test_a_scheduled_run_reports_last_listing_only_the_pages_it_created():
    assert ROUTINE, "no §10 for the scheduled run's report"
    assert "after §7's last close" in ROUTINE
    assert "stage=routine" in ROUTINE and "written_from=written.json" in ROUTINE
    # `close` stamps the job's `job` and `meta` on every listed page, so a
    # page the run only edited — a same-day rerun's report among them — is
    # never listed.
    assert "created with `page create`" in ROUTINE
    assert "same-day rerun edited" in ROUTINE and "only edited" in ROUTINE and "the HTML" in ROUTINE


def test_the_schedule_it_names_is_the_ops_morning_job():
    assert "`ops-morning` job" in BODY
    assert "bundle" not in BODY
