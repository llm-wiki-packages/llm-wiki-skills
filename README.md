# llm-wiki-skills

Skills for [llm-wiki](https://github.com/simple10/llm-wiki-plugins) wikis. The ops CLI reads this repo as a **package**: `llm-wiki-ops skills install llm-wiki-packages/llm-wiki-skills@<name>` copies a unit from here into a wiki (`skills search <task>` finds one), and `llm-wiki-package.json` is the list of what ships.

```toml
# .llm-wiki.toml — this package is the default when nothing is declared
[[packages]]
source = "llm-wiki-packages/llm-wiki-skills"
version = "latest"
```

- `skills/<name>/` — a skill unit: `SKILL.md`, `manifest.json`, `references/enable.md`, `references/customize.md`, `scripts/`, `tests/`. A channel unit's manifest declares `harvest` and `process` as model-session stages; a unit like `web-page` declares a single `script` stage instead, a plain `.py` run with no model session. A unit's references are served inside a wiki by `llm-wiki-ops reference <name>/<file>`, enabled copy first, committed source otherwise.
- `skills/<name>/tests/` — the unit's own tests: its scripts against its fixtures, no CLI. They ship with the unit, so an agent in a wiki can run them from the enabled copy: `uv run --with pytest pytest <ops dir>/skills/<name>/tests -p no:cacheprovider` — one unit per invocation; the cache would read as drift
- `tests/` — the package's: the harness (every unit installed and enabled through the real CLI, each stage run by the runner in its jail with the harness profile's fake agent as the session, `test_<venue>_harness.py`), the manifests, the docs gate, and what has to hold across every unit
- `references/sandboxes/<venue>/<venue>.harvest.md` — the sandbox a unit's `stages.harvest.sandbox_ref` names: its hosts, bins, credential and profile snippet
- `scripts/check-manifest.py` — the manifest agrees with the tree
- `scripts/release.py` — cut a release: `bump patch|minor|major` in a PR, then `tag` on a synced main pushes `v<version>`. Wikis pin these tags; never cut one by hand

Authoring a unit: `llm-wiki-ops reference skill-authoring` prints the contract inside any wiki.
