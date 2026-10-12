# channel-youtube — after enabling

1. Declare the job, naming the skill: `llm-wiki-ops jobs add
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
   llm-wiki-ops credentials set youtube kind=dir login=browser host=youtube.com
   llm-wiki-ops credentials login youtube
   llm-wiki-ops credentials bind job <slug> dir=youtube
   ```

   Use a throwaway Google account, and never open that profile in a browser
   again: YouTube rotates the session's cookies under any open tab, and the
   harvest's own copy (`cookies.txt` in the credential directory) would stop
   working. A harvest that fails with `auth` means the session is dead: run
   `credentials login youtube` again and the next harvest re-exports from
   the fresh profile. Public videos need none of this. Bind the job, not
   the skill: a skill's `dir` is handed to every job of the skill, so answer
   `none` when `/llm-wiki:enable` asks for the skill's dir slot.
