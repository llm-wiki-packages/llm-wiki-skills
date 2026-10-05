# channel-youtube-watch-gemini — after enabling

1. **Bind a Gemini key**, at a terminal: create one at
   https://aistudio.google.com/apikey, store it, and bind it to the job's
   slug. The value arrives on stdin; never on a command line.

   ```sh
   llm-wiki-ops credentials set gemini
   llm-wiki-ops credentials bind <slug> gemini
   ```

   Without a binding the job's enrich stage is unclaimable on this machine.
2. **Tell the operator what leaves the machine.** The video's url and the
   question go to Google, which watches the video under its own API terms. The
   key sits in the wiki's credential store, never in a file this unit names.
   Only a public YouTube video works: a private, age-gated or non-YouTube one
   fails or is skipped, because nothing is downloaded or uploaded.
3. **Declare the job**, naming `channel-youtube` as the skill and this unit
   as the enrich skill. An enrich unit is never a job's `skill=`: the CLI
   refuses it there once the unit is enabled:

   ```sh
   llm-wiki-ops pipeline jobs add <video-url> slug=<video-name> description="<what this is>" skill=channel-youtube enrich.skill=channel-youtube-watch-gemini
   ```

   An existing `channel-youtube` job gets it with `llm-wiki-ops pipeline jobs
   edit <slug> enrich.skill=channel-youtube-watch-gemini`. The job's `enrich.options.question=` and
   `enrich.options.model=` steer it. Install `channel-youtube` as well: it
   writes the page, and without it there is nothing to carry the notes.
4. **Run it**, jailed, through the runner: `llm-wiki-ops pipeline run
   job=<slug> wait=<s>` harvests the video, then enriches it, then writes the
   page. `llm-wiki-ops pipeline tickets show <id>` names a failed enrich's reason.
5. **A smoke test before binding a key to a job**, from the catalog's own
   checkout, outside any wiki and at your own terminal, with a throwaway key in
   the environment of the one command:

   ```sh
   GEMINI_API_KEY=<key> python3 skills/channel-youtube-watch-gemini/scripts/watch_gemini.py --item <youtube url> --capture-dir <scratch dir>
   ```

   It prints `{"status": "ok", ...}` and leaves `watch.md` under `enrich/`.

Unverified: the jailed run, where the bound key is read inside the enrich
sandbox, has not been exercised against the live API.
