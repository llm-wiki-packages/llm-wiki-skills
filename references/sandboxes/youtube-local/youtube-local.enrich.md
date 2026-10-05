# youtube-local.enrich

The sandbox for the `enrich` stage of `channel-youtube-watch-local`. A model
session that fetches the video at low resolution with yt-dlp, cuts stills with
ffmpeg and looks at them.

## Bins

`yt-dlp`, `ffmpeg` and `ffprobe`, recorded by `skills enable`; the floor
read-grants the slice their bin dirs.

## Hosts

- `youtube.com`: the apex.
- `*.youtube.com`: `www.youtube.com`, the watch page and the player.
- `youtu.be`: short links.
- `*.googlevideo.com`: the media streams.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Credential

None.

## Customize

- yt-dlp writes a cache under `$HOME/.cache/yt-dlp`, which this sandbox
  does not grant. Unverified whether a denied cache costs more than a
  warning; if a fetch fails on it, a `filesystem.allow` on that directory is
  the fix.
- `*.ytimg.com` is left out: no thumbnail is fetched. Unverified; if yt-dlp is
  denied there, add it.

## Never loosen

Do not widen to `*.google.com` or `*`: yt-dlp's reach is these hosts.

## Profile

```jsonc
// youtube-local.enrich: the jail of the local-watch enrich stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "youtube-local-enrich",
      "description": "the local-watch enrich slice: the video hosts."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue.
        "youtube.com",
        "*.youtube.com",
        "youtu.be",
        "*.googlevideo.com"
      ]
    }
  }
}
```
