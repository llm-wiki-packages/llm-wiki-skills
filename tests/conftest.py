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


def _cli_bin(ops: list) -> list:
    """The directory of a CLI named by path, for PATH. A venue route's capture
    mints its argv from the durable `llm-wiki-cli`, found on PATH when no
    durable home holds it, and the scratch HOME holds none: `uv run` put its
    venv's `bin` there, a console script named directly does not."""
    return [str(Path(ops[-1]).parent)] if os.sep in ops[-1] else []


# The gated rows the harness's own calls ask. A test home's `[approvals]` answers them
# silently, the plugins suites' way, so no case here meets the gate it is not about:
# the operator's knob (the plugins' machine-config contract), set on a throwaway home.
SILENCED = (
    "credentials bind",
    "credentials remove",
    "credentials set",
    "credentials unbind",
    "join",
    "machine wikis vault",
    "skills enable",
    "skills install",
)


@pytest.fixture(scope="session")
def env(ops) -> dict:
    # Every CLI call reads this box's machine home: a scratch one, so the suite
    # never touches the real machine's. `LLM_WIKI_TEST_HOME` names it, which only
    # a CLI run from a plugins checkout with a `checkout` record honors; an
    # installed CLI resolves its install's home whatever it is told, so the
    # install tier refuses to run on one (below). uv keeps its real cache.
    machine_home = SCRATCH / "home"
    machine_home.mkdir()
    uv_cache = subprocess.run(["uv", "cache", "dir"], capture_output=True, text=True, check=True).stdout.strip()
    e = dict(os.environ)
    # A suite started from inside a wiki session must not act on THAT wiki:
    # `LLM_WIKI_ROOT` binds one ahead of the `cwd=` a `run` case uses, and
    # `CLAUDE_PROJECT_DIR` — the harness's project dir, never a wiki root, and
    # read by no CLI — goes too, so nothing downstream mistakes it for one.
    # A test home the caller's own suite set is not this one.
    for ambient in ("LLM_WIKI_ROOT", "CLAUDE_PROJECT_DIR", "LLM_WIKI_TEST_HOME"):
        e.pop(ambient, None)
    e.update(
        HOME=str(machine_home),
        UV_CACHE_DIR=uv_cache,
        LLM_WIKI_PACKAGES_OFFLINE="1",
        GIT_AUTHOR_NAME="harness",
        GIT_AUTHOR_EMAIL="harness@example.invalid",
        GIT_COMMITTER_NAME="harness",
        GIT_COMMITTER_EMAIL="harness@example.invalid",
        # The session the runner names each slice's worker after
        # (`harness-session.<ticket>`), rather than one it would mint.
        LLM_WIKI_SESSION_ID="harness-session",
        PATH=os.pathsep.join([str(AGENT_DIR / "bin"), *_cli_bin(ops), e.get("PATH", os.defpath)]),
    )
    # Where the default layout puts a home, so the profile and sandbox base
    # `machine_harness` and `machine_layer` write land in it; its state, data
    # and cache dirs are its siblings.
    seeded = run(_cli(ops), e, "--json", "machine", "home", "init", str(machine_home / ".config" / "llm-wiki"), "--confirm")
    assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    dirs = seeded.data
    e["LLM_WIKI_TEST_HOME"] = dirs["home"]
    where = run(_cli(ops), e, "--json", "machine", "home")
    assert where.returncode == 0, where.stdout + where.stderr
    if where.data["source"] != "LLM_WIKI_TEST_HOME":
        refusal = (
            f"the ops CLI ({' '.join(ops)}) resolves the machine home {where.data['home']} "
            f"({where.data['source']}), not the scratch one: every install case would write this machine's own. "
            "Set LLM_WIKI_OPS to a plugins checkout's CLI, its `checkout` record written by its `scripts/checkout_home.py`"
        )
        if os.environ.get("LLM_WIKI_OPS"):
            pytest.fail(refusal)
        pytest.skip(refusal)
    config = Path(dirs["home"]) / "config.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + "\n[approvals]\n" + "".join(f'"{row}" = "silent"\n' for row in SILENCED),
        encoding="utf-8",
    )
    # The checkout as a developer's clone of this package: nothing fetches into
    # a symlinked marketplace, and `latest` is its HEAD.
    mp = Path(dirs["data"]) / "packages" / "marketplaces" / SOURCE
    mp.parent.mkdir(parents=True)
    mp.symlink_to(ROOT, target_is_directory=True)
    machine_harness(machine_home)
    return e


@pytest.fixture(scope="session")
def wiki(ops, env) -> Path:
    """One `init`ed wiki for the session — installs accumulate in it, which
    is what a real wiki does."""
    w = SCRATCH / "wiki" / "w"
    r = run(_cli(ops), env, "init", str(w), "preset=general")  # values are key=value; init commits on its own
    assert r.returncode == 0, r.stderr
    # `jobs add` needs a joined checkout. `join` registers the wiki in the
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
    # `[jobs.defaults] model` is the wiki's rung of the model chain, the one
    # ADR-0014 falls to where a unit declares no `stages.<stage>.model`.
    # `config set` names a two-part key and this one has three, so it is
    # hand-written and committed like a peer's edit.
    (w / ".llm-wiki.toml").write_text(
        (w / ".llm-wiki.toml").read_text(encoding="utf-8") + '\n[jobs.defaults]\nmodel = "harness-model"\n',
        encoding="utf-8",
    )
    r = run(ops, rooted(env, w), "git", "commit", ".llm-wiki.toml",
            "message=harness: a committed model of last resort", cwd=w)
    assert r.returncode == 0, r.stdout + r.stderr
    return w
