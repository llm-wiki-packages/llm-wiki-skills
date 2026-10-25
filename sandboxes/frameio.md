# frameio

The sandbox for the Frame.io venue's `harvest` stage. A Frame.io share's
harvest: the share page, its HLS and document-proxy streams, and yt-dlp's
media pull.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `frame.io`: the apex.
- `*.frame.io`: the share app (`next.frame.io`), the HLS host
  (`sahls.frame.io`) and the proxy host (`assets.frame.io`).

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which the capture scripts launch.

## Credential

None. A share link is its own authorization.

## Customize

- Nothing beyond the ticket's host, which joins at dispatch.

## Never loosen

Do not widen `*.frame.io` to a CDN wildcard; a host the proxy refused comes
back as `denied` and is the foreman's call.
