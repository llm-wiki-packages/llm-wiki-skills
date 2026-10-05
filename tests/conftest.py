"""The harness fixtures: the CLI, the environment and the session wiki every
install-tier case runs against. The code is `harness.py`'s.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from harness import AGENT_DIR, ROOT, SCRATCH, SOURCE, _cli, _ops_argv, machine_harness, machine_layer, rooted, run

@pytest.fixture(scope="session")
def ops() -> list:
    argv = _ops_argv()
    if not argv:
        pytest.skip("no ops CLI: set LLM_WIKI_OPS or put llm-wiki-ops on PATH")
    return argv


@pytest.fixture(scope="session")
def env(ops) -> dict:
    home = SCRATCH / "packages-home"
    home.mkdir()
    mp = home / "marketplaces" / SOURCE
    mp.parent.mkdir(parents=True)
    mp.symlink_to(ROOT, target_is_directory=True)
    # Every CLI call reads this box's config under HOME: a scratch one, so the
    # suite never touches the real machine's, and uv keeps its real cache.
    machine_home = SCRATCH / "home"
    machine_home.mkdir()
    machine_harness(machine_home)
    uv_cache = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    e = dict(os.environ)
    # A suite started from inside a wiki session must not act on THAT wiki:
    # `LLM_WIKI_ROOT` binds one ahead of the `cwd=` a `run` case uses, and
    # `CLAUDE_PROJECT_DIR` — the harness's project dir, never a wiki root, and
    # read by no CLI — goes too, so nothing downstream mistakes it for one.
    for ambient in ("LLM_WIKI_ROOT", "CLAUDE_PROJECT_DIR"):
        e.pop(ambient, None)
    e.update(
        HOME=str(machine_home),
        UV_CACHE_DIR=uv_cache,
        LLM_WIKI_PACKAGES_HOME=str(home),
        LLM_WIKI_PACKAGES_OFFLINE="1",
        LLM_WIKI_MACHINE_CONFIG=str(home / "no-machine-config.toml"),
        GIT_AUTHOR_NAME="harness",
        GIT_AUTHOR_EMAIL="harness@example.invalid",
        GIT_COMMITTER_NAME="harness",
        GIT_COMMITTER_EMAIL="harness@example.invalid",
        # The session the runner names each slice's worker after
        # (`harness-session.<ticket>`), rather than one it would mint.
        LLM_WIKI_SESSION_ID="harness-session",
        PATH=f"{AGENT_DIR / 'bin'}{os.pathsep}{e.get('PATH', os.defpath)}",
    )
    return e


@pytest.fixture(scope="session")
def wiki(ops, env) -> Path:
    """One `init`ed wiki for the session — installs accumulate in it, which
    is what a real wiki does."""
    w = SCRATCH / "wiki" / "w"
    r = run(_cli(ops), env, "init", str(w), "preset=general")  # values are key=value; init commits on its own
    assert r.returncode == 0, r.stderr
    # `pipeline add` needs a joined checkout. `join` registers the wiki in the
    # throwaway machine config above and seeds this box's sandbox base under
    # `env`'s scratch HOME. It is a protected write: nobody is at a terminal
    # for this harness process, so it asks and refuses unless the session is
    # marked attended.
    join_env = {**env, "LLM_WIKI_SESSION_ATTENDED": "1"}
    r = run(ops, join_env, "join", "key=harness", cwd=w)
    assert r.returncode == 0, r.stdout + r.stderr
    machine_layer(ops, Path(env["HOME"]), env["UV_CACHE_DIR"])
    # A wiki must declare its packages with a pinned version, and `@latest`
    # names a release tag a shallow CI checkout does not carry: pin this
    # checkout's own commit, which the marketplace link above serves.
    sha = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    r = run(ops, rooted(env, w), "packages", "install", f"{SOURCE}@{sha}", cwd=w)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, rooted(env, w), "git", "commit", ".llm-wiki.toml",
            "message=harness: declare this checkout's package", cwd=w)
    assert r.returncode == 0, r.stdout + r.stderr
    # `[pipeline] model` is the committed fallback ADR-0014 falls to where a
    # unit declares no `stages.<stage>.model` (plugins main, post-#2487) — a
    # `config set` writes the LOCAL manifest only, and this key is read from
    # the COMMITTED one, so it is hand-written and committed like a peer's edit.
    (w / ".llm-wiki.toml").write_text(
        (w / ".llm-wiki.toml").read_text(encoding="utf-8") + '\n[pipeline]\nmodel = "harness-model"\n',
        encoding="utf-8",
    )
    r = run(ops, rooted(env, w), "git", "commit", ".llm-wiki.toml",
            "message=harness: a committed model of last resort", cwd=w)
    assert r.returncode == 0, r.stdout + r.stderr
    return w
