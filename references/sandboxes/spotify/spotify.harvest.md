# spotify.harvest

The sandbox for the Spotify venue's `harvest` stage. A Spotify show, episode
or playlist's metadata, its cover art, and the keyless iTunes lookup that
finds a show's open RSS feed.

## Bins

None.

## Hosts

- `spotify.com`: the apex.
- `*.spotify.com`: the Web API, the token endpoint and the embed page.
- `*.scdn.co`: cover art (`mosaic.scdn.co`, `i.scdn.co`).
- `*.spotifycdn.com`: cover art (`image-cdn-*.spotifycdn.com`).
- `itunes.apple.com`: the keyless feed lookup.

The model endpoints are the harness profile's; see `llm-wiki-ops reference
harness`.

## Credential

A venue route, `spotify`, in this sandbox's `## Machine` block below:
`upstream` `https://accounts.spotify.com`, `env_var` `SPOTIFY_TOKEN_AUTH`,
`credential_format` `"Basic {}"`, and one endpoint rule, `POST /api/token`.
`sandboxes enable` asks the operator before it writes the fragment to this
machine's allow file; a peer's commit grants nothing by itself. The route is
the stage's, never the harness profile's.

The route carries the client-credentials grant, not an API token. Its value
is the wiki's own, in its credential vault under the route's name: the app's
`<client_id>:<client_secret>`, base64-encoded, once per machine that
harvests (`references/enable.md` of `channel-spotify` has the line). `sandboxes
compose` adds the `credential_key` and the capture that read that name, so
the fragment carries neither. `requires.credential` is `false`: nothing is
bound to a job and no payload file is granted.

In the jail `SPOTIFY_TOKEN_AUTH` holds a phantom. `spotify.py` sends it as
the token request's `Authorization: Basic …`; the proxy puts the real value
there, on that one request to `accounts.spotify.com`. The client secret never
enters the jail. The bearer token Spotify answers is short-lived and stays in
the script's memory, sent to `api.spotify.com` alone. With no route the
capture runs keyless and says so.

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

## Profile

```jsonc
// spotify.harvest: the jail of a Spotify harvest stage.
{
  "v": 1,
  "profile": {
    "meta": {
      "name": "spotify-harvest",
      "description": "the Spotify harvest slice: this venue's hosts."
    },
    "network": {
      // Allow-list mode: naming any host denies every other.
      "allow_domain": [
        // The venue.
        "spotify.com",
        "*.spotify.com",
        "*.scdn.co",
        "*.spotifycdn.com",
        "itunes.apple.com"
      ]
    }
  }
}
```

## Machine

The venue route, as a nono fragment `skills install` writes to the
template's `machine.allow`. Nothing in it names a machine path. No probe:
the unit declares no bin to run one with.

```json
{
  "network": {
    "credentials": ["spotify"],
    "custom_credentials": {
      "spotify": {
        "upstream": "https://accounts.spotify.com",
        "env_var": "SPOTIFY_TOKEN_AUTH",
        "credential_format": "Basic {}",
        "endpoint_rules": [{"method": "POST", "path": "/api/token"}]
      }
    }
  }
}
```
