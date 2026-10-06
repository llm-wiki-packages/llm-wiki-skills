"""Export a bound browser profile's YouTube cookies as a Netscape `cookies.txt`.

    <browser_python> export_cookies.py <profile_dir> <out_file>

Run by the ticket's `browser_python` (the browser runtime's Python, which has
Playwright), from `capture_video.py` when the profile holds no jar yet; never
by `llm-wiki-ops run`. YouTube rotates an account's cookies whenever a browser
tab holds the session, so a jar yt-dlp shares with a live browser dies within
minutes. Exporting once and letting yt-dlp alone hold the session (it writes
rotated cookies back into `--cookies`) keeps the login good, which is why the
profile is opened here headless, read, and closed, and never reopened by the
unit.

Only cookies for YouTube, Google and the media CDN are written. The file is
0600, written whole through a temp file then renamed. No cookies for those
domains: exit 2 with one stderr line, the caller's `credential_store_error`.
"""

from __future__ import annotations

import os
import sys
import tempfile

HEADER = "# Netscape HTTP Cookie File\n"
DOMAINS = ("youtube.com", "google.com", "googlevideo.com")
# The flags the plugin's `browser_login.py` launches with, so the profile opens as it was written.
LAUNCH = {
    "args": ["--disable-blink-features=AutomationControlled"],
    "ignore_default_args": ["--enable-automation"],
}


def wanted(domain: str) -> bool:
    host = domain.lstrip(".").lower()
    return any(host == d or host.endswith("." + d) for d in DOMAINS)


def netscape_line(cookie: dict) -> str:
    domain = cookie["domain"]
    expires = cookie.get("expires", -1)
    expiry = 0 if expires is None or expires < 0 else int(expires)
    return "\t".join([
        domain,
        "TRUE" if domain.startswith(".") else "FALSE",
        cookie.get("path") or "/",
        "TRUE" if cookie.get("secure") else "FALSE",
        str(expiry),
        cookie["name"],
        cookie.get("value", ""),
    ])


def read_cookies(profile_dir: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(profile_dir, headless=True, **LAUNCH)
        try:
            return list(context.cookies())
        finally:
            context.close()


def write_jar(out_file: str, cookies: list[dict]) -> None:
    body = HEADER + "".join(netscape_line(c) + "\n" for c in cookies)
    directory = os.path.dirname(os.path.abspath(out_file)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".cookies-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        os.chmod(tmp, 0o600)
        os.replace(tmp, out_file)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: export_cookies.py <profile_dir> <out_file>", file=sys.stderr)
        return 2
    profile_dir, out_file = argv
    cookies = [c for c in read_cookies(profile_dir) if wanted(c.get("domain", ""))]
    if not cookies:
        print(f"the profile holds no cookies for {', '.join(DOMAINS)}: not logged in to youtube.com", file=sys.stderr)
        return 2
    write_jar(out_file, cookies)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
