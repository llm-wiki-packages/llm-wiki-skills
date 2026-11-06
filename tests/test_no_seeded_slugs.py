"""No unit's prose names a seeded job slug as the place to look or edit."""

from __future__ import annotations

import re

from harness import ROOT

SEEDED = re.compile(r"ops-(hourly|nightly|morning|denials|ingest|mine|synthesize|transcribe|narrate)(-host)?\b")
DOCS = sorted((ROOT / "skills").rglob("*.md"))


def test_no_unit_doc_names_a_seeded_job_slug():
    assert DOCS, "no unit docs found"
    hits = [f"{p.relative_to(ROOT)}:{n}" for p in DOCS
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if SEEDED.search(line)]
    assert not hits, hits


def test_no_unit_doc_spells_the_short_verbose_flag():
    hits = [str(p.relative_to(ROOT)) for p in DOCS if "jobs ls -v" in p.read_text(encoding="utf-8")]
    assert not hits, hits
