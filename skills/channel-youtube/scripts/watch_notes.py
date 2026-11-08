"""What an enrich unit left beside the capture, as the process step reads it.

`youtube_note.py` calls `load` and renders what it returns. The files are
`enrich/watch.md` and `enrich/watch.json` in the capture directory, written by
`channel-youtube-watch-gemini` or `channel-youtube-watch-local`; their shape is
`references/note-shape.md`. A missing, malformed or empty pair is no notes at
all, so a page reads as harvest alone would have built it.

Stdlib only; imports nothing from the plugin.
"""

import json
from pathlib import Path

NOTES_DIR = "enrich"
NOTES_NAME = "watch.md"
META_NAME = "watch.json"
ENGINES = ("gemini", "local")
MODEL_MAX = 80
# The enrich units cut at the same ceiling; a longer file is someone else's.
MAX_CHARS = 60_000


def load(cap_dir) -> dict | None:
    """`{"engine", "model", "text"}`, or None where there is nothing to fold in."""
    notes = Path(cap_dir) / NOTES_DIR
    # A link is something other than what an enrich unit wrote.
    if any(path.is_symlink() for path in (notes, notes / META_NAME, notes / NOTES_NAME)):
        return None
    try:
        meta = json.loads((notes / META_NAME).read_text(encoding="utf-8"))
        text = (notes / NOTES_NAME).read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    if not isinstance(meta, dict) or meta.get("v") != 1 or meta.get("engine") not in ENGINES:
        return None
    text = text.strip()[:MAX_CHARS]
    if not text:
        return None
    model = meta.get("model")
    return {
        "engine": meta["engine"],
        "model": model.strip()[:MODEL_MAX] if isinstance(model, str) and model.strip() else None,
        "text": text,
    }
