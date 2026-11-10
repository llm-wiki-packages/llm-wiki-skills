# channel-youtube — after enabling

1. Declare the job, naming the skill: `{{@brain-cli-ops}} jobs add
   <video-url> slug=<video-name>
   description="<what this is>" skill=channel-youtube` — the skill's manifest
   supplies the rest (`every=once`, `harvest.scope=page`,
   `harvest.assets=reference`, and a `dest` of `sources/youtube/<slug>`), so
   add `harvest.assets=download` only if the operator chose downloads. Single
   videos are the proven shape; channel/playlist enumeration is untested (see
   the SKILL.md's Discovery section).

2. Optional — private, age-restricted or members-only videos need a signed-in
   YouTube session. Store a browser-profile credential, sign in once in the
   jailed browser it opens, and bind it to the job:

   ```sh
   {{@brain-cli-ops}} credentials set youtube kind=dir login=browser host=youtube.com
   {{@brain-cli-ops}} credentials login youtube
   {{@brain-cli-ops}} credentials bind job <slug> dir=youtube
   ```

   Use a throwaway Google account, and never open that profile in a browser
   again: YouTube rotates the session's cookies under any open tab, and the
   session the harvest saves back would stop working. A harvest that fails
   with `auth` means the session is dead: run `credentials login youtube`
   again and the next harvest spends the fresh login. Public videos need none of this. Bind the job, not
   the skill: a skill's `dir` is handed to every job of the skill.
   `skills enable`, which `/{{@brain-plugin}}:enable` runs, maps nothing
   and lists the skill's `dir` slot as unmapped with a `bind skill` line;
   leave that line unrun.

3. Optional — watch notes. Name an enrich unit and the page carries a
   "Watch notes" section written from the video itself:
   `{{@brain-cli-ops}} jobs edit <slug> enrich.skill=channel-youtube-watch-gemini`
   (Google's model watches it; needs a key) or
   `enrich.skill=channel-youtube-watch-local` (frames and captions read on this
   machine). Each unit's own `references/enable.md` is the setup; keep
   `skill=channel-youtube` on the job, and never put an enrich unit there.
   Enrich is a stage of the rail, not an extra: a job that names one waits on
   it, and a capture whose enrich keeps failing stays out of process.
