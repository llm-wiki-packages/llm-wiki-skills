"""The package harness, as plain code: every test runs the REAL ops CLI
against a throwaway wiki, with this checkout served as the package. The
fixtures are `conftest.py`'s; everything a test imports is here, so each
module loads once (pytest loads `conftest` itself as a plugin, and a
`from conftest import` under importlib mode would load a second copy).

    LLM_WIKI_OPS   the ops CLI to run (a command line; default: `llm-wiki-ops`
                   on PATH). Absent → the install tests skip, saying so.

The checkout is symlinked as `marketplaces/<owner>/<repo>` under a tmp
packages home, which the CLI treats as a developer's clone: `latest` is
this checkout's HEAD — commit before you run — and nothing fetches.
`LLM_WIKI_PACKAGES_OFFLINE` is set, so nothing here touches the network.
"""

from __future__ import annotations

import ast
import atexit
import contextlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "llm-wiki-package.json").read_text(encoding="utf-8"))
SOURCE = MANIFEST["repository"]
SKILLS = [a["name"] for a in MANIFEST["artifacts"] if a["type"] == "skill"]
TEMPLATES = ROOT / "sandboxes"

# The `{{@brain-…}}` tokens `skills enable` and `reference` fill in a unit's
# `*.md` (the `unit-manifest` contract's Tokens section). The CLI names are
# permanent; `brain` is the plugin namespace.
TOKENS = {"brain-plugin": "brain", "brain-cli": "llm-wiki-cli", "brain-cli-ops": "llm-wiki-ops", "brain-cli-search": "llm-wiki-search"}
_TOKEN_OPEN = re.compile(r"\{\{@(@?)brain-")
_TOKEN_KEY = re.compile(r"(brain-[a-z-]*)\}\}")


def render(text: str, *, where: str = "<text>") -> str:
    """`text` as an enabled copy reads it. `{{@@brain-` is a literal
    `{{@brain-`; any other `{{@…}}` passes through; a bad token inside the
    namespace raises, naming `where` and the line."""
    out, at = [], 0
    for m in _TOKEN_OPEN.finditer(text):
        out.append(text[at : m.start()])
        if m.group(1):
            out.append("{{@brain-")
            at = m.end()
            continue
        key = _TOKEN_KEY.match(text, m.start() + 3)
        if not key or key.group(1) not in TOKENS:
            line = text.count("\n", 0, m.start()) + 1
            seen = text[m.start() :].split("\n", 1)[0][:40]
            raise ValueError(f"{where}:{line}: {seen!r} is not a token; the keys are " + ", ".join(f"{{{{@{k}}}}}" for k in TOKENS))
        out.append(TOKENS[key.group(1)])
        at = key.end()
    out.append(text[at:])
    return "".join(out)


def doc(path: Path) -> str:
    """A shipped `*.md`, rendered as the wiki reads it."""
    return render(path.read_text(encoding="utf-8"), where=str(path.relative_to(ROOT)))


def unit_manifest(name: str) -> dict:
    art = next(a for a in MANIFEST["artifacts"] if a["type"] == "skill" and a["name"] == name)
    return json.loads((ROOT / art["path"] / "manifest.json").read_text(encoding="utf-8"))


def _ops_argv() -> list | None:
    spec = os.environ.get("LLM_WIKI_OPS")
    if spec:
        return shlex.split(spec)
    exe = shutil.which("llm-wiki-ops")
    return [exe] if exe else None


def _cli(ops: list) -> list:
    """The machine CLI, out of the same command line. `init` is the one verb
    outside both scopes — it acts on a directory that is not a wiki yet, so it
    has no root to be dispatched with — and both scripts ship in one
    distribution, so only the last word differs. A path-spelled last word
    keeps its directory: the dispatch sets `LLM_WIKI_OPS` to the console
    script by ABSOLUTE path (the plugins' `env` contract), and `which` answers
    one too, and that directory need not be on PATH."""
    last = ops[-1]
    return [*ops[:-1], str(Path(last).with_name("llm-wiki-cli")) if os.sep in last else "llm-wiki-cli"]


# `run()` starts every call here, never in pytest's cwd: the CLI is root-bound
# and the cwd's owner must agree with `LLM_WIKI_ROOT`'s, so a checkout that
# sits INSIDE a wiki would have every `rooted()` call refused at the first
# fixture, as an opaque error. A directory nobody owns binds nothing.
NEUTRAL_CWD = Path(tempfile.mkdtemp(prefix="llm-wiki-harness-cwd-"))
atexit.register(shutil.rmtree, NEUTRAL_CWD, ignore_errors=True)

# The scratch HOME and the session wiki live here, never under `/tmp`: on Linux
# nono's `system_write_linux` group grants `/tmp` whole, Landlock has no deny
# primitive, and the runner refuses to start a jail whose base-layer denies
# (`$HOME/.ssh`, `$WORKDIR/.git/hooks`) sit under that grant.
SCRATCH = Path.home() / ".cache" / "llm-wiki-skills-harness" / f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
SCRATCH.mkdir(parents=True)
atexit.register(shutil.rmtree, SCRATCH, ignore_errors=True)

# Where the fake agent and every ticket's plan live: the one directory the
# machine layer grants every jail a read of, outside the wiki, so a jailed
# session cannot rewrite what it was told to do.
AGENT_DIR = SCRATCH / "harness-bin"
FAKE_AGENT = Path(__file__).with_name("fake_agent.sh")
# First on the harness's PATH as `bin/yt-dlp`, `bin/ntn`, `bin/gws` and `bin/parentsquare-mcp`: see each file.
FAKE_YT_DLP = Path(__file__).with_name("fake_yt_dlp.sh")
FAKE_NTN = Path(__file__).with_name("fake_ntn.sh")
FAKE_GWS = Path(__file__).with_name("fake_gws.sh")
FAKE_PARENTSQUARE_MCP = Path(__file__).with_name("fake_parentsquare_mcp.sh")
YT_FIXTURES = AGENT_DIR / "yt"


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str

    @property
    def data(self):
        return json.loads(self.stdout)


def run(ops: list, env: dict, *args, cwd=None, input=None) -> Result:
    cp = subprocess.run([*ops, *args], env=env, cwd=cwd or NEUTRAL_CWD, capture_output=True, text=True, check=False, input=input)
    return Result(cp.returncode, cp.stdout, cp.stderr)


def rooted(env: dict, wiki: Path) -> dict:
    """The environment that binds a call to `wiki`. The CLI is root-bound and
    no verb takes a wiki argument: `LLM_WIKI_ROOT` names the wiki a caller
    standing outside it means, and it must be ABSOLUTE. A `run` child owns its
    whole argv, so that one verb binds by `cwd=` instead — and a case that
    stands inside the wiki may pass both, because they agree."""
    return {**env, "LLM_WIKI_ROOT": str(Path(wiki).resolve())}


def machine_harness(home: Path) -> Path:
    """The machine's default harness profile, pointing at the fake agent: a
    session stage's jail starts it where a real box starts `claude`, with no
    agent binary on PATH and no login route. Beside it, the `yt-dlp`, `ntn` and `gws`
    stand-ins the harness's PATH leads with, a git identity, uv set offline, and
    `bins.jsonc` naming `uv`, which `run` needs for a script with PEP 723
    dependencies and a jail's PATH does not carry."""
    AGENT_DIR.mkdir(parents=True, exist_ok=True)
    agent = AGENT_DIR / FAKE_AGENT.name
    shutil.copy2(FAKE_AGENT, agent)
    agent.chmod(0o755)
    (AGENT_DIR / "bin").mkdir(exist_ok=True)
    (AGENT_DIR / "bin" / "yt-dlp").write_text(
        FAKE_YT_DLP.read_text(encoding="utf-8").replace("@YT_FIXTURES@", shlex.quote(str(YT_FIXTURES))), encoding="utf-8")
    (AGENT_DIR / "bin" / "yt-dlp").chmod(0o755)
    shutil.copy2(FAKE_NTN, AGENT_DIR / "bin" / "ntn")
    (AGENT_DIR / "bin" / "ntn").chmod(0o755)
    shutil.copy2(FAKE_GWS, AGENT_DIR / "bin" / "gws")
    (AGENT_DIR / "bin" / "gws").chmod(0o755)
    shutil.copy2(FAKE_PARENTSQUARE_MCP, AGENT_DIR / "bin" / "parentsquare-mcp")
    (AGENT_DIR / "bin" / "parentsquare-mcp").chmod(0o755)
    profile = home / ".config" / "llm-wiki" / "harnesses" / "claude.jsonc"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(json.dumps({"v": 1, "harness": {"command": [str(agent), "{prompt}"]}}), encoding="utf-8")
    # The exit pass commits as the host's git identity; a scratch HOME has none.
    (home / ".gitconfig").write_text("[user]\n\tname = harness\n\temail = harness@example.invalid\n", encoding="utf-8")
    # uv offline, from the cache the CI warm step fills: a slice has no route
    # to an index, and nothing in this suite reaches the network.
    (home / ".config" / "uv").mkdir(parents=True, exist_ok=True)
    (home / ".config" / "uv" / "uv.toml").write_text("offline = true\n", encoding="utf-8")
    uv = shutil.which("uv")
    if uv:
        (home / ".config" / "llm-wiki" / "bins.jsonc").write_text(json.dumps({"uv": uv}), encoding="utf-8")
    return profile


def _cli_python(ops: list) -> list:
    """The interpreter the ops CLI runs under, out of the same command line."""
    last = ops[-1]
    if os.sep in last:
        return [*ops[:-1], str(Path(last).resolve().with_name("python"))]
    return [*ops[:-1], "python"]


_TOOLCHAIN = """
import json, os, sys, llm_wiki_ops
roots = [sys.prefix, sys.base_prefix, os.path.dirname(os.path.dirname(llm_wiki_ops.__file__)), os.path.dirname(os.path.realpath(sys.executable))]
roots += [p for p in sys.path if p and os.path.isdir(p)]
from llm_wiki_ops.lib.errors import Refused
from llm_wiki_ops.lib.plugin_root import plugin_root  # the plugin's own scripts, which a slice runs; an ImportError is loud
try:
    roots.append(str(plugin_root()))
except Refused:
    # Only a wheel with no plugin tree beside it and no variable naming one is
    # tolerated; a variable that names a bad directory is a refusal to surface.
    if os.environ.get("LLM_WIKI_PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT"):
        raise
print(json.dumps(sorted({r for root in roots for r in (root, os.path.realpath(root))})))
"""


def machine_layer(ops: list, home: Path, uv_cache: str) -> None:
    """The machine layer every jail is composed over, as an operator would
    write it for this box: read grants to exec the ops CLI (its venv,
    interpreter and import roots, read off the CLI's own interpreter) and the
    plugin root, to read the fake agent's `AGENT_DIR`, `uv`, `bins.jsonc` and
    `uv.toml`; and, in the slice layer, a uv cache a jail may write. `run`
    executes a PEP 723 script under `uv run --script`, which cannot start on a
    read-only cache, and the floor write-denies the default one
    (llm-wiki-plugins #1630, finding 8): a cache the slice layer names is the
    operator's way through, and the one this box takes."""
    done = subprocess.run([*_cli_python(ops), "-c", _TOOLCHAIN], cwd=NEUTRAL_CWD, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    reads = [*json.loads(done.stdout.strip().splitlines()[-1]), str(AGENT_DIR)]
    uv = shutil.which("uv")
    if uv:
        reads += [str(home / ".config" / "llm-wiki" / "bins.jsonc"), str(home / ".config" / "uv" / "uv.toml"),
                  str(Path(uv).parent), str(Path(uv).resolve().parent)]
    path = home / ".config" / "llm-wiki" / "sandbox" / "base.jsonc"
    document = jsonc(path.read_text(encoding="utf-8")) if path.is_file() else {"v": 1, "profile": {}}
    filesystem = document["profile"].setdefault("filesystem", {})
    filesystem["read"] = sorted({*filesystem.get("read", []), *reads})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    # A slice's own layer: the base file carries no write grant a jail honors.
    path.with_name("slice.jsonc").write_text(json.dumps({"v": 1, "profile": {"filesystem": {"allow": [uv_cache]}}}), encoding="utf-8")


def outbound_ip() -> str:
    """This box's own outbound-routable address — NOT necessarily a public
    one (found the hard way: on a NAT'd CI runner it is a private 10.x/
    172.16.x/192.168.x address, and `ticket_host.of` refuses that as a job
    target exactly as it should: "names this machine or a private
    network"). A UDP `connect` never sends a packet; it only asks the
    routing table which local address would carry one to `host`, so this
    needs no reachability and touches no network. Useful only for binding
    a harness's own local `http.server` somewhere this box's own traffic
    can reach — callers that also need the RESULT to pass `ticket_host`'s
    guard must check `is_globally_routable` themselves, or use
    `RESOLVABLE_TEST_HOST` instead where no real reachability is needed."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]


def is_globally_routable(ip: str) -> bool:
    """Whether `ticket_host.of`/`reaches_public` would accept `ip` as a job's
    target — the same `ipaddress.is_global` test the plugin itself runs."""
    import ipaddress

    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False


# A real, IANA-reserved public domain (RFC 2606): `ticket_host.of` accepts any
# DNS name that is not `localhost`/`*.localhost`, unconditionally — WHAT it
# resolves to is `reaches_public`'s question, asked through the box's own
# system resolver, with no override seam in the plugin (`common/resolver.py`
# imports no network module beyond `socket.getaddrinfo` and reads no env var).
# This name resolves to a real, stable, globally-routable address wherever
# there is DNS/internet egress at all — unlike `outbound_ip()`, it does not
# depend on THIS box's own address being public, so it is what a case uses
# when it only needs the dispatch GATE to pass (a fixture-only capture that
# never actually fetches the target) rather than a real, reachable server.
RESOLVABLE_TEST_HOST = "example.com"


def jsonc(text: str) -> object:
    """JSON with `//` line comments, which the catalog's sandbox templates carry. A `//`
    inside a string (a url in a description) is not a comment."""
    out, in_string, i = [], False, 0
    while i < len(text):
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        else:
            out.append(c)
        i += 1
    return json.loads("".join(out))


def template(name: str) -> dict:
    """The catalog's sandbox template `sandboxes/<name>.jsonc`, parsed."""
    return jsonc((TEMPLATES / f"{name}.jsonc").read_text(encoding="utf-8"))


def template_name(unit: str) -> str:
    """The template a unit's unit-level `sandbox_ref` names: `<package>:<name>`."""
    package, name = unit_manifest(unit)["sandbox_ref"].rsplit(":", 1)
    assert package == SOURCE, f"{unit}: sandbox_ref {package!r} names a package other than this one"
    return name


def installed_sandbox(ops: list, env: dict, wiki: Path, unit: str) -> dict:
    """The `sandbox.jsonc` `skills install` wrote into the unit's tree in `wiki`, parsed."""
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    return jsonc((wiki / ops_dir / "skills" / unit / "sandbox.jsonc").read_text(encoding="utf-8"))


# What `skills enable` asks beyond the ordinary yes, per unit: the dangerous
# tokens the unit's sandbox names, which `accept=` answers in an attended session.
ACCEPT = {"daily-report": ".git"}

# A unit whose sandbox probe spends a mapped route at enable: the route's name
# and the one host its value may be spent at. The probe runs in the composed
# jail, where the route's variable holds the phantom only once it is mapped.
PROBE_SPENDS = {"channel-notion-tasks": ("notion", "api.notion.com")}


def enabled(ops: list, env: dict, wiki: Path, name: str) -> None:
    """The unit, installed and enabled in the session wiki — by whichever case
    gets there first. Install writes the unit's `sandbox.jsonc` and validates
    it; enable is the gate. Each verb is a no-op over an identical copy, so a
    case that needs the unit asks for it rather than leaning on another
    having run (`-k`, `--lf`, a shuffled or split run)."""
    r = run(ops, rooted(env, wiki), "--json", "skills", "install", name)
    assert r.returncode == 0, r.stdout + r.stderr
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    argv = ["--json", "skills", "enable", name, "--confirm", *([f"accept={ACCEPT[name]}"] if name in ACCEPT else [])]
    with contextlib.ExitStack() as stack:
        if name in PROBE_SPENDS:
            route, host = PROBE_SPENDS[name]
            stack.enter_context(local_vault(ops, env))
            stack.callback(unmapped_route, ops, env, wiki, name, route)
            mapped_route(ops, env, wiki, name, route, host, value="harness-probe")
        r = run(ops, attended, *argv)
        assert r.returncode == 0, r.stdout + r.stderr


@dataclass
class Job:
    slug: str
    dest: str
    record: dict


def bound_credential(ops: list, env: dict, wiki: Path, slug: str, name: str | None = None, value: str = "harness-credential") -> str:
    """A `"required"` file slot's claim gate, satisfied for job `slug` on this
    session (references/enable.md): `credentials set <name>` (stdin — never a
    command-line argument), then `credentials bind job <slug> file=<name>` —
    `bind` refuses a name not set here first. The VALUE is unread by
    everything, so any placeholder does (enable.md). Returns `name`."""
    name = name or f"{slug}-cred"
    # Both are protected writes: nobody is at a terminal for this harness
    # process, so each asks and refuses unless the session is marked attended.
    attended_env = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    r = run(ops, attended_env, "--json", "credentials", "set", name, input=value)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, attended_env, "--json", "credentials", "bind", "job", slug, f"file={name}")
    assert r.returncode == 0, r.stdout + r.stderr
    return name


@contextlib.contextmanager
def local_vault(ops: list, env: dict):
    """The session wiki's vault named `local` for the `with` block, by the
    line the enable notes give, `llm-wiki-cli machine wikis vault harness
    local`, attended as the operator runs it. The provider reads a route's
    value through it, at bind, at spawn and on each request, so a case holds
    it across all three. The config is put back as it was found, so no case
    leans on another having named the vault."""
    config = Path(env["LLM_WIKI_MACHINE_CONFIG"])
    before = config.read_bytes()
    r = run(_cli(ops), {**env, "LLM_WIKI_SESSION_ATTENDED": "1"}, "--json", "machine", "wikis", "vault", "harness", "local")
    assert r.returncode == 0, r.stdout + r.stderr
    try:
        yield
    finally:
        config.write_bytes(before)


def mapped_route(ops: list, env: dict, wiki: Path, unit: str, route: str, host: str, value: str = "harness-token") -> str:
    """`unit`'s venue route `route` mapped on this machine, the way its
    references/enable.md says: the value stored under the route's name with
    the one host it may be spent at, then `credentials bind skill`. The caller
    holds `local_vault`, which `bind` reads. Returns the stored value."""
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    r = run(ops, attended, "--json", "credentials", "set", route, input=json.dumps({"value": value, "host": host}))
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, attended, "--json", "credentials", "bind", "skill", unit, f"{route}={route}")
    assert r.returncode == 0, r.stdout + r.stderr
    return value


def unmapped_route(ops: list, env: dict, wiki: Path, unit: str, route: str) -> None:
    """`mapped_route` undone, for a `finally`: the skill's mapping dropped and
    the stored value removed. A case that stopped early may have made
    neither, so neither refusal is an error here."""
    attended = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    run(ops, attended, "--json", "credentials", "unbind", "skill", unit)
    run(ops, attended, "--json", "credentials", "remove", route)


def declared_job(ops: list, env: dict, wiki: Path, unit: str, target: str, *extra: str, slug: str | None = None) -> Job:
    """A real job for `unit` in the session wiki, declared the way
    references/enable.md says to (A-11: `jobs add`/`jobs show`) — the pass
    that lands a capture reads the job it belongs to, so a
    capture with no job behind it is refused. Idempotent for one
    (slug, target) pair; a wiki holds ONE job per target and a slug names one
    source for good, so a case wanting a job of its own passes both."""
    enabled(ops, env, wiki, unit)
    slug = slug or f"port-{unit}"
    # `dest` and `every` are both required now (plugins main, post-#2487): a
    # job needs where its pages land and how often it pulls. A caller that
    # wants its own passes `dest=`/`every=` in `extra`.
    if not any(e.startswith("dest=") for e in extra):
        extra = (*extra, f"dest=sources/harness/{slug}")
    if not any(e.startswith("every=") for e in extra):
        extra = (*extra, "every=once")
    # `transcribe` is a host ENGINE section every job carries by default
    # (`job_schema`; a unit reaches it only through `watch.defaults`), so `close` on a harvest
    # `ok` routes through a transcribe ticket first, media or not, and only
    # the transcribe DRAIN (this box's own, not a case here) lands it on to
    # `process`. Most units declare no `transcribe` (hubspot and spotify tune
    # it, four directory-body units ship it null), so every harness job nulls
    # the section at declare time — one real hop, harvest to process, the
    # shape `advanced()` assumes. A catalog default is read by a case that
    # calls `jobs add` itself, without this stdin.
    r = run(ops, rooted(env, wiki), "--json", "jobs", "add", target, f"slug={slug}", f"skill={unit}", f"description=port: {unit}", *extra, "--stdin", input='{"transcribe": null}')
    assert r.returncode == 0, r.stdout + r.stderr
    record = run(ops, rooted(env, wiki), "--json", "jobs", "show", slug).data["job"]
    return Job(slug, record["dest"], record)


def claimed(ops: list, env: dict, wiki: Path, job: Job) -> tuple[str, Path]:
    """A real harvest ticket, minted pending by `jobs claim <slug>`, and the
    capture directory its stage will be started in, read back through
    `tickets show`. The job is then paused: the pass a slice's exit runs
    lands the ticket and would start the next one with no plan written yet,
    and a paused job's tickets start only when `staged` names them."""
    r = run(ops, rooted(env, wiki), "--json", "jobs", "claim", job.slug)
    assert r.returncode == 0, r.stdout + r.stderr
    paused = run(ops, rooted(env, wiki), "--json", "jobs", "pause", job.slug)
    assert paused.returncode == 0, paused.stdout + paused.stderr
    mine = [c for c in r.data["claimed"] if c["slug"] == job.slug]
    assert mine and mine[0]["tickets"], f"{job.slug}: claim minted no ticket: {r.stdout}"
    ticket_id = mine[0]["tickets"][0]["id"]
    return ticket_id, capture_of(ops, env, wiki, ticket_id)


def capture_of(ops: list, env: dict, wiki: Path, ticket: str) -> Path:
    r = run(ops, rooted(env, wiki), "--json", "tickets", "show", ticket)
    assert r.returncode == 0, r.stdout + r.stderr
    return wiki / r.data["tickets"][0]["capture_dir"]


@dataclass
class Session:
    """What a stage's jailed session left: `tickets run`'s answer and the
    slice log, which holds the fake agent's output between the runtime's own
    lines."""

    answer: dict
    log: str

    @property
    def update(self) -> dict | None:
        """The last `tickets update` the stage posted, as the runner read it at exit."""
        return self.answer["wait"]["table"][0]["update"]

    def step(self, name: str) -> Result:
        """One `step` of the plan: its exit code, stdout and stderr."""
        for line in self.log.splitlines():
            if line.startswith(STEP_MARK):
                said = json.loads(line[len(STEP_MARK):])
                if said["name"] == name:
                    return Result(said["rc"], said["out"], said["err"])
        raise AssertionError(f"the session ran no step {name!r}:\n{self.log[-4000:]}")


# What every plan starts with. `step NAME CMD...` runs one command the way a
# session types it and prints its exit code, stdout and stderr as ONE JSON
# line behind `STEP_MARK`, in one write: the runtime logs into the same file,
# and a line it writes cannot land inside a step's output. Run by the CLI's
# own interpreter, which every jail is granted. No temporary file: a jail may
# write `/tmp` and still not read it back. `OPS` is the CLI the spawn hands
# the jail; `FIX` is the case's fixtures, under `AGENT_DIR`.
STEP_MARK = "@@step "
_STEP_PY = """\
import json, subprocess, sys
try:
    done = subprocess.run(sys.argv[2:], capture_output=True)
    rc, out, err = done.returncode, done.stdout, done.stderr
except OSError as exc:
    rc, out, err = 127, b"", str(exc).encode()
line = {"name": sys.argv[1], "rc": rc, "out": out.decode("utf-8", "replace"), "err": err.decode("utf-8", "replace")}
sys.stdout.write(%r + json.dumps(line) + "\\n")
""" % STEP_MARK
PLAN_HEAD = """\
OPS="$LLM_WIKI_OPS"
PY="$(dirname "$LLM_WIKI_OPS")/python"
TICKET={ticket}
CAP={capture}
FIX={fixtures}
export OPS PY TICKET CAP FIX
step() {{
    "$PY" -c {step_py} "$@"
}}
cd "$LLM_WIKI_ROOT"
"""

# The runner's own words where this machine has no sandbox runtime at all.
# Nothing else skips: a jail the runner refuses to compose is a failure.
NO_JAIL = "no sandbox runtime on this machine"


def no_jail_here(answer: Result) -> None:
    """Skip, quoting the runner, where this machine has no runtime to start a stage's jail with."""
    text = answer.stdout + answer.stderr
    if NO_JAIL in text:
        at = text.index(NO_JAIL)
        pytest.skip(f"this machine cannot start a stage's jail, so no stage runs here: {text[at:at + 300]}")


# llm-wiki-plugins #3080: what stops a stage inside its slice on plugins main,
# each in the plugin's own words, read off the slice log. `tickets update` and
# the plugin's `extract.py` open the wiki root for listing, which a Linux slice
# is not granted (the root by its own path, so no other refusal matches); and
# since #3072 `run` asks `git ls-files` about `.agents/` with the slice's own
# `GIT_DIR`, and git answers "not a git repository". A case that meets either
# has nothing left to prove on this box.
def plugin_refused(wiki: Path, text: str) -> None:
    refusals = {
        f"PermissionError: [Errno 13] Permission denied: '{Path(wiki).resolve()}'":
            "a Linux slice cannot list the wiki root, so `tickets update` and `extract.py` die on it",
        "`git ls-files` failed (128) rather than saying whether .agents/ is tracked": "`run` refuses every unit script in a slice: `git ls-files` there answers 'not a git repository'",
    }
    for words, why in refusals.items():
        if words in text:
            pytest.skip(f"llm-wiki-plugins #3080: {why}; the case runs where that is fixed")


def staged(ops: list, env: dict, wiki: Path, ticket: str, plan: str, files: dict | None = None, wait: str = "120s") -> Session:
    """Run `ticket`'s stage the one way a unit's stage runs: `tickets
    run <id> wait=` starts it behind the jail the runner composes, and the
    harness profile's command, the fake agent, stands in for the session and
    types `plan` there. `files` (name -> bytes) are the case's fixtures,
    readable in the jail under `$FIX`. Skips, quoting the runner, where this
    machine cannot start a jail. Returns once the pass the worker's exit runs
    has landed the ticket."""
    fixtures = AGENT_DIR / f"fix.{ticket}"
    fixtures.mkdir(parents=True, exist_ok=True)
    for name, data in (files or {}).items():
        (fixtures / name).parent.mkdir(parents=True, exist_ok=True)
        (fixtures / name).write_bytes(data)
    capture = capture_of(ops, env, wiki, ticket).relative_to(wiki)
    head = PLAN_HEAD.format(ticket=shlex.quote(ticket), capture=shlex.quote(str(capture)), fixtures=shlex.quote(str(fixtures)),
                            step_py=shlex.quote(_STEP_PY))
    (AGENT_DIR / f"plan.{ticket}.sh").write_text(head + plan, encoding="utf-8")
    r = run(ops, rooted(env, wiki), "--json", "tickets", "run", ticket, f"wait={wait}")
    no_jail_here(r)
    assert r.returncode == 0, r.stdout + r.stderr
    waited = r.data.get("wait") or {}
    assert waited.get("event") == "exit", f"{ticket}: the stage did not exit within {wait}: {r.stdout}"
    log = Path(waited["table"][0]["log"]).read_text(encoding="utf-8", errors="replace")
    plugin_refused(wiki, log)
    # `wait=` answers at the worker's exit; the pass that exit runs lands the
    # ticket (and mints the next stage's) a moment later.
    deadline = time.monotonic() + 60
    while shown(ops, env, wiki, ticket)["state"] == "active":
        assert time.monotonic() < deadline, f"{ticket}: still active 60s after its worker exited"
        time.sleep(0.5)
    return Session(r.data, log)


def shown(ops: list, env: dict, wiki: Path, ticket: str) -> dict:
    """The ticket's record. A landing moves it between queue directories, and
    a `show` in that moment reads it `missing`: asked again, briefly."""
    for _ in range(20):
        r = run(ops, rooted(env, wiki), "--json", "tickets", "show", ticket)
        assert r.returncode == 0, r.stdout + r.stderr
        if r.data["tickets"]:
            return r.data["tickets"][0]
        time.sleep(0.25)
    raise AssertionError(f"{ticket}: `tickets show` keeps answering it missing: {r.stdout}")


def pending(ops: list, env: dict, wiki: Path, slug: str, stage: str = "process") -> dict[str, str]:
    """The tickets the landing of a job's last stage minted for `stage`, still
    pending: `{capture_dir: id}`. The pass a slice's exit runs is what lands it."""
    r = run(ops, rooted(env, wiki), "--json", "tickets", "ls")
    assert r.returncode == 0, r.stdout + r.stderr
    ids = [t["id"] for t in r.data["tickets"] if t["slug"] == slug and t["stage"] == stage and t["state"] == "pending"]
    return {shown(ops, env, wiki, one)["capture_dir"]: one for one in ids}


def unit_tests(unit: str, module: str) -> dict:
    """A shipped test module's namespace — helpers, constants, imports —
    without its tests. A unit's tests ship with it (`skills/<unit>/tests/`)
    and know nothing of this harness; the harness tier for that unit lives
    here and reads exactly as it did beside them, by taking their names.
    `test_*` stays out, or pytest would collect those cases a second time;
    so does everything the module merely imported (the stdlib, pytest), which
    a harness file imports for itself — a name borrowed from another file's
    import list is a NameError the day that file stops needing it."""
    path = ROOT / "skills" / unit / "tests" / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"_unit_tests_{unit}_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    imported = {
        alias.asname or alias.name.split(".")[0]
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    return {k: v for k, v in vars(mod).items() if not k.startswith("__") and not k.startswith("test_") and k not in imported}
