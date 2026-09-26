import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# No global git config: a machine that signs tags or commits would prompt.
ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=ENV).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--quiet", "--bare", "-b", "main", str(remote))
    work = tmp_path / "work"
    (work / "scripts").mkdir(parents=True)
    (work / "skills").mkdir()
    for name in ("release.py", "check-manifest.py"):
        shutil.copy(ROOT / "scripts" / name, work / "scripts" / name)
    manifest = {"schema_version": 1, "name": "pkg", "version": "0.1.0", "artifacts": []}
    (work / "llm-wiki-package.json").write_text(json.dumps(manifest, indent=2) + "\n")
    git(work, "init", "--quiet", "-b", "main")
    git(work, "commit", "--quiet", "--allow-empty", "-m", "seed")
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", "package")
    git(work, "remote", "add", "origin", str(remote))
    git(work, "push", "--quiet", "origin", "main")
    return work, remote


def release(work: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(work / "scripts" / "release.py"), *args], cwd=work, capture_output=True, text=True, env=ENV)


def version(work: Path) -> str:
    return json.loads((work / "llm-wiki-package.json").read_text())["version"]


def test_tag_pushes_the_manifest_version(repo):
    work, remote = repo
    r = release(work, "tag")
    assert r.returncode == 0, r.stderr
    assert git(remote, "tag", "--list") == "v0.1.0"


def test_tag_dry_run_creates_nothing(repo):
    work, remote = repo
    assert release(work, "tag", "--dry-run").returncode == 0
    assert git(work, "tag", "--list") == ""


def test_tag_refuses_a_version_already_released(repo):
    work, _ = repo
    assert release(work, "tag").returncode == 0
    r = release(work, "tag")
    assert r.returncode == 1 and "already exists" in r.stderr


def test_tag_refuses_a_dirty_tree(repo):
    work, _ = repo
    (work / "stray").write_text("x")
    r = release(work, "tag")
    assert r.returncode == 1 and "not clean" in r.stderr


def test_tag_refuses_main_not_at_the_remote(repo):
    work, _ = repo
    git(work, "commit", "--quiet", "--allow-empty", "-m", "local only")
    r = release(work, "tag")
    assert r.returncode == 1 and "pull first" in r.stderr


@pytest.mark.parametrize(("to", "want"), [("patch", "0.1.1"), ("minor", "0.2.0"), ("major", "1.0.0"), ("0.3.0", "0.3.0")])
def test_bump_writes_the_next_version(repo, to, want):
    work, _ = repo
    assert release(work, "bump", to).returncode == 0
    assert version(work) == want


def test_bump_refuses_a_version_not_above_the_newest_release(repo):
    work, _ = repo
    assert release(work, "tag").returncode == 0
    r = release(work, "bump", "0.1.0")
    assert r.returncode == 1 and "not above" in r.stderr
    assert version(work) == "0.1.0"
