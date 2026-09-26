#!/usr/bin/env python3
"""Cut a release: a `v<semver>` tag on main at the manifest's `version`.

    scripts/release.py bump patch|minor|major|X.Y.Z   write the next version into the manifest
    scripts/release.py tag [--dry-run]                tag main at that version and push the tag

A release is two steps because the version lands through a PR like any other
change: `bump` on a branch, merge, then `tag` on a synced main. A wiki pins a
release tag, so a tag is never moved or reused — `tag` refuses one that
exists, and a version that is not above the newest release.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "llm-wiki-package.json"
SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")
RELEASE_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
VERSION_LINE = re.compile(r'("version"\s*:\s*")([^"]*)(")')


class Refused(Exception):
    pass


def git(*args: str) -> str:
    cp = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {cp.stderr.strip() or cp.stdout.strip()}")
    return cp.stdout.strip()


def parse(version: str) -> tuple[int, int, int]:
    m = SEMVER.fullmatch(version)
    if not m:
        raise Refused(f"{version!r} is not X.Y.Z")
    return tuple(int(part) for part in m.groups())


def manifest_version() -> str:
    version = json.loads(MANIFEST.read_text(encoding="utf-8")).get("version", "")
    parse(version)
    return version


def released() -> list[tuple[int, int, int]]:
    tags = git("tag", "--list", "v*").splitlines()
    return sorted(tuple(int(p) for p in m.groups()) for t in tags if (m := RELEASE_TAG.fullmatch(t)))


def bump(to: str) -> str:
    current = parse(manifest_version())
    major, minor, patch = current
    new = {
        "major": (major + 1, 0, 0),
        "minor": (major, minor + 1, 0),
        "patch": (major, minor, patch + 1),
    }.get(to) or parse(to)
    floor = max([current, *released()])
    if new <= floor:
        raise Refused(f"{'.'.join(map(str, new))} is not above {'.'.join(map(str, floor))}")
    text = MANIFEST.read_text(encoding="utf-8")
    version = ".".join(map(str, new))
    updated, count = VERSION_LINE.subn(lambda m: m.group(1) + version + m.group(3), text)
    if count != 1:
        raise Refused(f"{MANIFEST.name}: expected one \"version\" line, found {count}")
    MANIFEST.write_text(updated, encoding="utf-8")
    return version


def tag(remote: str, dry_run: bool) -> str:
    git("fetch", "--quiet", "--tags", remote, "main")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise Refused("not on main — a release is cut from main")
    if git("status", "--porcelain"):
        raise Refused("the working tree is not clean")
    if git("rev-parse", "HEAD") != git("rev-parse", f"{remote}/main"):
        raise Refused(f"main is not {remote}/main — pull first")
    check = subprocess.run([sys.executable, str(ROOT / "scripts" / "check-manifest.py")], capture_output=True, text=True)
    if check.returncode != 0:
        raise Refused(f"check-manifest.py failed:\n{check.stderr.strip()}")
    version = manifest_version()
    name = f"v{version}"
    if git("tag", "--list", name):
        raise Refused(f"{name} already exists — bump the version first")
    newest = released()
    if newest and parse(version) <= newest[-1]:
        raise Refused(f"{name} is not above the newest release v{'.'.join(map(str, newest[-1]))}")
    if not dry_run:
        git("tag", "-a", name, "-m", name)
        git("push", "--quiet", remote, f"refs/tags/{name}")
    return name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bump", help="write the next version into the manifest")
    b.add_argument("to", help="patch, minor, major, or X.Y.Z")
    t = sub.add_parser("tag", help="tag main at the manifest's version and push the tag")
    t.add_argument("--dry-run", action="store_true", help="check everything, create and push nothing")
    t.add_argument("--remote", default="origin")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "bump":
            version = bump(args.to)
            print(f"{MANIFEST.name}: version {version} — commit it through a PR, then `scripts/release.py tag` on main")
        else:
            name = tag(args.remote, args.dry_run)
            print(f"{name}: would tag {git('rev-parse', '--short', 'HEAD')}" if args.dry_run else f"{name}: tagged and pushed")
    except Refused as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
