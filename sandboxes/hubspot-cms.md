# hubspot-cms

The sandbox for the HubSpot CMS venue's `harvest` stage. A HubSpot CMS
page whose content is a HubSpot Video: the page renders in Chromium through
Playwright, and the Mux stream behind the player is fetched.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `play.hubspotvideo.com`: the lazy player iframe.
- `image.mux.com`: the storyboard that names the playback id.
- `stream.mux.com`: the unsigned master playlist.
- `*.mux.com`: the rendition hosts behind the master
  (`manifest-*.edgemv.mux.com`); the exact set is unverified.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Filesystem

`machine_reads: playwright-cache`: read on Playwright's browser build
(`$HOME/.cache/ms-playwright` on Linux, `$HOME/Library/Caches/ms-playwright`
on macOS), which the capture scripts launch.

## Credential

None.

## Customize

- The site's own host is the ticket's and joins at dispatch.
- A Playwright install outside the default cache
  (`PLAYWRIGHT_BROWSERS_PATH`) is not reached: `playwright-cache` names the
  default directories only, and a stage entry cannot name a machine path.

## Never loosen

Add no site host here: the platform's hosts are the same for every HubSpot
customer, and a site is the ticket's.
