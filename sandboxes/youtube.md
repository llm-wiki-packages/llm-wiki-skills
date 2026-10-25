# youtube

The sandbox for the YouTube venue's `harvest` stage. A YouTube video's
metadata, captions and media, fetched by yt-dlp.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `youtube.com`: the apex.
- `*.youtube.com`: `www.youtube.com`, the watch page and the player.
- `youtu.be`: short links.
- `*.googlevideo.com`: the media streams.
- `*.ytimg.com`: thumbnails.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Filesystem

`machine_reads: yt-dlp-cache`: read on yt-dlp's cache directory
(`$HOME/.cache/yt-dlp`).

## Credential

`requires.credentials.dir` is `"optional"`: unbound, the stage runs keyless and reaches
public videos only. Bound, the slot holds a `dir` credential with `login:
browser` — a Chromium profile a person signed in to YouTube on through
`credentials login`, which the ticket hands over as `credential_dir`
(granted read-write to this slice) with `browser_python` beside it. A slot
and not a route: yt-dlp reads cookies off disk, and no proxy can inject a
browser session.

yt-dlp takes cookies only; there is no OAuth or password route. The unit
exports a Netscape `cookies.txt` into that same directory once (through
`browser_python`, the profile opened headless and closed again) and passes
`--cookies <dir>/cookies.txt` to every yt-dlp call from then on. yt-dlp
writes the cookies YouTube rotates back into that file, so the directory must
stay writable and the jar, not the profile, is the live session: no failure
deletes it. The unit reopens the browser profile only to export again: when
there is no usable jar, or when the profile's cookie DB is newer than the
jar, which is what a `credentials login` since the last export looks like. A browser tab holding
the same session would rotate the cookies out from under yt-dlp. Nothing
from the directory lands in the capture dir.

Use a throwaway account: yt-dlp's own wiki warns that a harvesting account
can be rate-limited or banned.

## Customize

- yt-dlp writes a cache under `$HOME/.cache/yt-dlp`. The stage reads it
  (`machine_reads: yt-dlp-cache`) and cannot write it: a stage entry cannot
  name a machine path. Unverified whether a read-only cache costs more than
  a warning.

## Never loosen

Do not widen to `*.google.com` or `*`: yt-dlp's reach is these hosts.
