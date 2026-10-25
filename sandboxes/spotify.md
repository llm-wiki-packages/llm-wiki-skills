# spotify

The sandbox for the Spotify venue's `harvest` stage. A Spotify show, episode
or playlist's metadata, its cover art, and the keyless iTunes lookup that
finds a show's open RSS feed.

`process` and `routine` add nothing to their stock bases.

## Hosts

- `spotify.com`: the apex.
- `*.spotify.com`: the Web API, the token endpoint and the embed page.
- `*.scdn.co`: cover art (`mosaic.scdn.co`, `i.scdn.co`).
- `*.spotifycdn.com`: cover art (`image-cdn-*.spotifycdn.com`).
- `itunes.apple.com`: the keyless feed lookup.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Credential

A venue route, `spotify`, on the harvest stage: `upstream`
`https://accounts.spotify.com`, `env_var` `SPOTIFY_TOKEN_AUTH`,
`credential_format` `"Basic {}"`, and one endpoint rule, `POST /api/token`.
`skills enable` lists the route among the stage's hosts and routes before the
operator's yes; a peer's commit grants nothing by itself. The route is the
stage's, never the harness profile's.

The route carries the client-credentials grant, not an API token. Its value
is the wiki's own, in its credential vault: the app's
`<client_id>:<client_secret>`, base64-encoded, stored with the host
`accounts.spotify.com` and mapped to the route's name once per machine that
harvests, after the vault is named (`references/enable.md` of
`channel-spotify` has the lines). `sandboxes compose` adds the
`credential_key` and the capture that read the mapped name, so the template
carries neither. The manifest leaves the binding undeclared, which reads
`"optional"`, and declares no `file` or `dir`, so no payload file is
granted.

In the jail `SPOTIFY_TOKEN_AUTH` holds a phantom. `spotify.py` sends it as
the token request's `Authorization: Basic …`; the proxy puts the real value
there, on that one request to `accounts.spotify.com`. The client secret never
enters the jail. The bearer token Spotify answers is short-lived and stays in
the script's memory, sent to `api.spotify.com` alone. A machine that maps
nothing runs the stage with the route omitted, and the capture runs keyless
and says so.

## Customize

- A show's own feed and enclosure hosts, if the operator wants its audio
  fetched in a slice rather than by a widen (`references/enable.md`, the
  known limitation).

## Never loosen

- Never add a DRM media host: music and Spotify-exclusive audio are captured
  as references and never ripped.
- Add no route to the harness profile for this venue, and no
  `SPOTIFY_CLIENT_ID`/`SPOTIFY_CLIENT_SECRET` to any environment: the route
  is the one way the grant reaches a capture.
