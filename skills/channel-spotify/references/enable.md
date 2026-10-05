# channel-spotify — after enabling

1. **API access** — needed for guaranteed-complete item lists (public
   catalog only; no user login exists in this skill). It is the harvest
   sandbox's `spotify` route (`sandboxes enable` asks before it writes the
   route to this machine's allow file), and its value is the wiki's own, in
   its credential vault. Have the operator create an app at
   developer.spotify.com → Dashboard; then the OPERATOR runs this at a
   terminal, once per machine that harvests:

   ```sh
   tr -d '\n' | base64 | tr -d '\n'; echo
   llm-wiki-ops credentials set spotify
   ```

   The first line reads `<client_id>:<client_secret>` typed at the terminal
   (Enter, then Ctrl-D) and prints the grant, base64 of that pair; the second
   asks for the value without echo — paste the grant there. Neither puts it in
   an argument (argv is readable in `ps` and lands in shell history), and
   `credentials set` asks only at a terminal: its stdin is not a pipe. In the harvest's jail the
   route's variable holds a phantom, and the proxy adds the grant only to the
   token request bound for `accounts.spotify.com`. With the route enabled and
   no grant stored, the token request fails and the harvest says so; with no
   route the capture degrades to the keyless embed fallback: possibly-truncated
   item lists, flagged `"keyless": true` and with a warning callout in the note.
2. **Non-URL requests** ("add the Lex Fridman podcast episode 400"): ask the
   operator for the entity's Spotify URL, then watch that. Nothing in this
   unit searches the catalog.
3. **Declare the job**: one per entity URL.
   `llm-wiki-ops pipeline jobs add <entity-url> slug=<content-name>
   description="<what this is>" skill=channel-spotify
   meta.group="<name>" meta.group_type=playlist|series` — a playlist or show
   is a bundle. open.spotify.com is a generic share host carrying no source
   identity, so name the slug after the content. The skill's manifest supplies
   `every=once`, `harvest.scope=page` (the capture enumerates the entity's
   items itself — there is no link crawling), `harvest.assets=download` and a
   `dest` of `sources/podcasts/<slug>`; pass `dest=` to land it elsewhere.
   One `skill=channel-spotify` covers both stages: this skill renders its own
   venue's page into `dest`.
   **A show or playlist the operator wants RE-pulled for new episodes needs
   two more keys**: `every=<period> harvest.refresh=<period>`. The container
   URL is the job's one page, so once it is held every later pull is
   `skipped`; only a refresh ticket re-captures it, and the host mints those
   from `harvest.refresh` (`never`, the default, or a period — and it refuses
   a refresh period on an `every=once` job). Ask which the operator wants: a
   one-time snapshot (the defaults) or a followed show.
4. **Set audio expectations**: downloads happen only when the content is
   openly distributed (podcast episodes matched to their show's public
   RSS feed). Music tracks and Spotify-exclusive audio are captured as
   `drm_protected` references with full metadata — never ripped.

## Known limitation — media egress under a confined harvest

The harvest stage's sandbox reference covers the Spotify endpoints, Spotify's
cover-art CDNs (`*.scdn.co`, `*.spotifycdn.com` — the cover is an asset of
every capture) and the keyless iTunes feed lookup, and deliberately nothing
more: the open-audio
route ends at the creator's own RSS feed and MP3 enclosure (one show's
lookup resolves to `https://lexfridman.com/feed/podcast/`), and those hosts
differ per show and are not known when the host computes the session's
egress. A confined harvest therefore reaches metadata and the feed lookup
and fails the download with a named allowlist refusal. The gap is
deliberate — do not try to finish the allowlist.

## The route, and nothing else

This skill declares `requires.credential: false`: a job is bound to no
credential and its slice is granted no payload file. The `spotify` route is
the one way the grant reaches a capture, and the script calls no
`credentials` verb. A route in a harness profile, or `SPOTIFY_CLIENT_ID` in
an environment, reaches nothing here. Unverified live: no capture has run
against Spotify through the route.
