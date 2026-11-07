"""The `ops.` keys the units write are ones the real `page create` takes."""

from __future__ import annotations

import pytest

from harness import rooted, run


@pytest.mark.parametrize("title,keys", [
    ("Video stub", ["ops.extracted=queued", "ops.media=_raw/x/video.mp4"]),
    ("Course root", ["ops.root=true", "ops.extract=light", "ops.edits=merge"]),
])
def test_page_create_takes_the_ops_keys_a_unit_writes(ops, env, wiki, title, keys):
    made = run(ops, rooted(env, wiki), "--json", "page", "create", f"title={title}", "dest=sources/opskeys", "type=document", *keys)
    assert made.returncode == 0, made.stdout + made.stderr
