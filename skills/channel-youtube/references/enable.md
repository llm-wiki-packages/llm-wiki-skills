# channel-youtube — after enabling

1. Declare the job, naming the skill: `llm-wiki-ops pipeline jobs add
   <video-url> slug=<video-name>
   description="<what this is>" skill=channel-youtube` — the skill's manifest
   supplies the rest (`every=once`, `harvest.scope=page`,
   `harvest.assets=reference`, and a `dest` of `sources/youtube/<slug>`), so
   add `harvest.assets=download` only if the operator chose downloads. Single
   videos are the proven shape; channel/playlist enumeration is untested (see
   the SKILL.md's Discovery section).
2. **Optional: watch notes.** Name an enrich unit and the page carries a
   "Watch notes" section written from the video itself:
   `llm-wiki-ops pipeline jobs edit <slug> enrich.skill=channel-youtube-watch-gemini`
   (Google's model watches it; needs a key) or
   `enrich.skill=channel-youtube-watch-local` (frames and captions read on this
   machine). Each unit's own `references/enable.md` is the setup; keep
   `skill=channel-youtube` on the job, and never put an enrich unit there.
   Enrich is a stage of the rail, not an extra: a job that names one waits on
   it, and a capture whose enrich keeps failing stays out of process.
