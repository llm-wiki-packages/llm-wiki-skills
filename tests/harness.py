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
# First on the harness's PATH as `bin/yt-dlp`: see the file.
FAKE_YT_DLP = Path(__file__).with_name("fake_yt_dlp.sh")
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
    agent binary on PATH and no login route. Beside it, the `yt-dlp` stand-in
    the harness's PATH leads with, a git identity, uv set offline, and
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
try:  # the plugin's own scripts, which a process slice runs: `extract.py`
    from llm_wiki_ops.commands.common.plugin_root import plugin_root
    roots.append(str(plugin_root()))
except Exception:
    pass
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
    """JSON with `//` line comments, which the sandbox snippets carry. A `//`
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


def snippet(reference: str) -> str:
    """The one fenced `jsonc` block of a sandbox reference: the profile a wiki
    sandbox is written from."""
    fences = re.findall(r"^```jsonc\n(.*?)^```$", reference, re.M | re.S)
    assert len(fences) == 1, f"a sandbox reference carries {len(fences)} jsonc blocks, not one"
    return fences[0]


def bound(ops: list, env: dict, wiki: Path, name: str) -> None:
    """Every stage of the installed unit that names a `sandbox_ref`, bound the
    way `/llm-wiki:sandbox` and `/llm-wiki:enable` do it: the reference read
    through the CLI, its snippet written and committed as a wiki sandbox, that
    sandbox enabled, the stage bound. A snippet key the policy reader does not
    admit fails here, at `sandboxes enable`."""
    ops_dir = run(ops, rooted(env, wiki), "--json", "whereami").data["wiki"]["ops_dir"]
    for stage, spec in unit_manifest(name).get("stages", {}).items():
        ref = spec.get("sandbox_ref")
        if not ref:
            continue
        package, rel = ref.rsplit(":", 1)
        r = run(ops, rooted(env, wiki), "--json", "reference", f"{package}:references/sandboxes/{rel}.md")
        assert r.returncode == 0, r.stdout + r.stderr
        sandbox = f"{name}-{stage}"
        template = wiki / ops_dir / "sandboxes" / f"{sandbox}.jsonc"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text(snippet(r.data["text"]), encoding="utf-8")
        for verb in (
            ["git", "commit", str(template.relative_to(wiki)), f"message=sandboxes: {sandbox} from {ref}"],
            ["sandboxes", "enable", sandbox, "--confirm"],
            ["skills", "bind", name, f"stage={stage}", f"sandbox={sandbox}", "--confirm"],
        ):
            r = run(ops, rooted(env, wiki), "--json", *verb)
            assert r.returncode == 0, r.stdout + r.stderr


def enabled(ops: list, env: dict, wiki: Path, name: str) -> None:
    """The unit, installed, bound and enabled in the session wiki — by
    whichever case gets there first. Each verb is a no-op over an identical
    copy, so a case that needs the unit asks for it rather than leaning on
    another having run (`-k`, `--lf`, a shuffled or split run)."""
    r = run(ops, rooted(env, wiki), "--json", "skills", "install", name)
    assert r.returncode == 0, r.stdout + r.stderr
    bound(ops, env, wiki, name)
    r = run(ops, rooted(env, wiki), "--json", "skills", "enable", name, "--confirm")
    assert r.returncode == 0, r.stdout + r.stderr


@dataclass
class Job:
    slug: str
    dest: str
    record: dict


def bound_credential(ops: list, env: dict, wiki: Path, slug: str, name: str | None = None, value: str = "harness-credential") -> str:
    """`requires.credential: true`'s claim gate, satisfied for `slug` on this
    session (references/enable.md): `credentials set <name>` (stdin — never a
    command-line argument), then `credentials bind <slug> <name>` — `bind`
    refuses a name not set here first. The VALUE is unread by everything, so
    any placeholder does (enable.md). Returns `name`."""
    name = name or f"{slug}-cred"
    # Both are protected writes: nobody is at a terminal for this harness
    # process, so each asks and refuses unless the session is marked attended.
    attended_env = {**rooted(env, wiki), "LLM_WIKI_SESSION_ATTENDED": "1"}
    r = run(ops, attended_env, "--json", "credentials", "set", name, input=value)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run(ops, attended_env, "--json", "credentials", "bind", slug, name)
    assert r.returncode == 0, r.stdout + r.stderr
    return name


def declared_job(ops: list, env: dict, wiki: Path, unit: str, target: str, *extra: str, slug: str | None = None) -> Job:
    """A real job for `unit` in the session wiki, declared the way
    references/enable.md says to (A-11: `jobs add`/`jobs show`) — `pipeline
    extract` reads the job a capture belongs to, so a
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
    # (`job_schema` — the unit never declares it), so `close` on a harvest
    # `ok` routes through a transcribe ticket first, media or not, and only
    # the transcribe DRAIN (this box's own, not a case here) lands it on to
    # `process`. None of this suite's units declare `transcribe`, so every
    # harness job nulls the section at declare time — one real hop, harvest
    # to process, the shape `advanced()` assumes.
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "add", target, f"slug={slug}", f"skill={unit}", f"description=port: {unit}", *extra, "--stdin", input='{"transcribe": null}')
    assert r.returncode == 0, r.stdout + r.stderr
    record = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "show", slug).data["job"]
    return Job(slug, record["dest"], record)


def claimed(ops: list, env: dict, wiki: Path, job: Job) -> tuple[str, Path]:
    """A real harvest ticket, minted pending by `jobs claim <slug>`, and the
    capture directory its stage will be started in, read back through
    `tickets show`. The job is then paused: the pass a slice's exit runs
    lands the ticket and would start the next one with no plan written yet,
    and a paused job's tickets start only when `staged` names them."""
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "claim", job.slug)
    assert r.returncode == 0, r.stdout + r.stderr
    paused = run(ops, rooted(env, wiki), "--json", "pipeline", "jobs", "pause", job.slug)
    assert paused.returncode == 0, paused.stdout + paused.stderr
    mine = [c for c in r.data["claimed"] if c["slug"] == job.slug]
    assert mine and mine[0]["tickets"], f"{job.slug}: claim minted no ticket: {r.stdout}"
    ticket_id = mine[0]["tickets"][0]["id"]
    return ticket_id, capture_of(ops, env, wiki, ticket_id)


def capture_of(ops: list, env: dict, wiki: Path, ticket: str) -> Path:
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "show", ticket)
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
        found = re.search(
            rf"^@@out {re.escape(name)}\n(.*?)\n@@err {re.escape(name)}\n(.*?)\n@@rc {re.escape(name)} (\d+)$",
            self.log, re.M | re.S,
        )
        assert found, f"the session ran no step {name!r}:\n{self.log[-4000:]}"
        out, err, rc = found.groups()
        return Result(int(rc), out, err)


# What every plan starts with. `step NAME CMD...` runs one command the way a
# session types it and prints its stdout, then its stderr and exit code, each
# behind a marker `Session.step` reads back off the log. No temporary file: a
# jail may write `/tmp` and still not read it back. `OPS` is the CLI the spawn
# hands the jail; `FIX` is the case's fixtures, under `AGENT_DIR`.
PLAN_HEAD = """\
OPS="$LLM_WIKI_OPS"
TICKET={ticket}
CAP={capture}
FIX={fixtures}
export OPS TICKET CAP FIX
step() {{
    name=$1; shift
    echo "@@out $name"
    {{ err=$("$@" 2>&1 1>&3 3>&-); rc=$?; }} 3>&1
    printf '\\n@@err %s\\n%s\\n@@rc %s %s\\n' "$name" "$err" "$name" "$rc"
}}
cd "$LLM_WIKI_ROOT"
"""

# The runner's own words where this machine cannot start a jail at all: no
# sandbox runtime on PATH, or a platform that cannot hold the composed denies.
NO_JAIL = ("no sandbox runtime", "no deny primitive")


def no_jail_here(answer: Result) -> None:
    """Skip, quoting the runner, where it could not start a stage's jail."""
    text = answer.stdout + answer.stderr
    for words in NO_JAIL:
        if words in text:
            at = text.index(words)
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
        f"Permission denied: '{Path(wiki).resolve()}'": "a Linux slice cannot list the wiki root, so `tickets update` and `extract.py` die on it",
        "`git ls-files` failed (128) rather than saying whether .agents/ is tracked": "`run` refuses every unit script in a slice: `git ls-files` there answers 'not a git repository'",
    }
    for words, why in refusals.items():
        if words in text:
            pytest.skip(f"llm-wiki-plugins #3080: {why}; the case runs where that is fixed")


def staged(ops: list, env: dict, wiki: Path, ticket: str, plan: str, files: dict | None = None, wait: str = "120s") -> Session:
    """Run `ticket`'s stage the one way a unit's stage runs: `pipeline tickets
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
    head = PLAN_HEAD.format(ticket=shlex.quote(ticket), capture=shlex.quote(str(capture)), fixtures=shlex.quote(str(fixtures)))
    (AGENT_DIR / f"plan.{ticket}.sh").write_text(head + plan, encoding="utf-8")
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "run", ticket, f"wait={wait}")
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
        r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "show", ticket)
        assert r.returncode == 0, r.stdout + r.stderr
        if r.data["tickets"]:
            return r.data["tickets"][0]
        time.sleep(0.25)
    raise AssertionError(f"{ticket}: `tickets show` keeps answering it missing: {r.stdout}")


def pending(ops: list, env: dict, wiki: Path, slug: str, stage: str = "process") -> dict[str, str]:
    """The tickets the landing of a job's last stage minted for `stage`, still
    pending: `{capture_dir: id}`. The pass a slice's exit runs is what lands it."""
    r = run(ops, rooted(env, wiki), "--json", "pipeline", "tickets", "ls")
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
