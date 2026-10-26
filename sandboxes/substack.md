# substack

The sandbox for the Substack venue's `harvest` stage. A Substack
publication's archive API, its posts, and the images on its CDN.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `substack.com`: the apex.
- `*.substack.com`: each publication's subdomain and `api.substack.com`.
- `substackcdn.com`: post images.

The model endpoints are the harness profile's; see `{{@brain-cli-ops}} reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which the capture scripts launch.

## Credential

None. Paid posts are recorded as paywalled, never fetched signed-in.

## Customize

- A custom-domain publication: its host is the ticket's own and joins at
  dispatch.

## Never loosen

Add no host a post did not name in a report's `missing[]`.
