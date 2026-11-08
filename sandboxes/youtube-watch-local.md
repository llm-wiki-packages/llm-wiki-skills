# youtube-watch-local

The sandbox for `channel-youtube-watch-local`. `enrich` is a model session
that fetches the video at low resolution with yt-dlp, cuts stills with
ffmpeg and reads them with the captions. `routine` adds nothing to its stock
base.

## Bins

`yt-dlp`, `ffmpeg` and `ffprobe`, recorded by `skills enable`; the floor
read-grants the slice their bin dirs.

## Hosts

- `youtube.com`: the apex.
- `*.youtube.com`: `www.youtube.com`, the watch page and the player.
- `youtu.be`: short links.
- `*.googlevideo.com`: the media streams.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}}
reference harness`.

## Filesystem

`machine_reads: yt-dlp-cache`: read on yt-dlp's cache directory
(`$HOME/.cache/yt-dlp`). The stage cannot write it. Unverified whether a
read-only cache costs more than a warning.

## Credential

None: only public videos are watched.

## Customize

- `*.ytimg.com` is left out: no thumbnail is fetched. Unverified; if yt-dlp
  is denied there, add it.

## Never loosen

Do not widen to `*.google.com` or `*`: yt-dlp's reach is these hosts.
