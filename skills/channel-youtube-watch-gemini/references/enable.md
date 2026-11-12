# {{@brain-unit}} — after enabling

1. **The key.** Create one at https://aistudio.google.com/apikey. On each
   machine that enriches, name the wiki's vault, `<key>` being this wiki's
   key in `{{@brain-cli}} machine wikis list`:

   ```sh
   {{@brain-cli}} machine wikis vault <key> local
   ```

   Store the key, never on a command line, as `{"value": "<key>", "host":
   "generativelanguage.googleapis.com"}` at the prompt:

   ```sh
   {{@brain-cli-ops}} credentials set gemini
   ```

   Then, once the skill is enabled, map the route:

   ```sh
   {{@brain-cli-ops}} credentials bind skill {{@brain-unit}} gemini=gemini
   ```

   `skills enable`, which `/{{@brain-plugin}}:enable` runs, maps nothing:
   it lists `gemini` as unmapped, with that line. The binding is
   `"required"`: until it is mapped, the enrich stage does not run on this
   machine. The sandbox's `## Credential` section spells the route out:

   ```sh
   {{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/youtube-watch-gemini.md
   ```

2. **Tell the operator what leaves the machine.** The video's url and the
   question go to Google, which watches the video under its own API terms.
   The key stays in the wiki's vault; the jail holds only a phantom. Only a
   public YouTube video works: a private, age-gated or non-YouTube one fails
   or is skipped, because nothing is downloaded or uploaded.

3. **Declare the job**, naming `channel-youtube` as the skill and this unit
   as the enrich skill. An enrich unit is never a job's `skill=`:

   ```sh
   {{@brain-cli-ops}} jobs add <video-url> slug=<video-name> description="<what this is>" skill=channel-youtube enrich.skill={{@brain-unit}}
   ```

   An existing `channel-youtube` job gets it with `{{@brain-cli-ops}} jobs
   edit <slug> enrich.skill={{@brain-unit}}`. The job's
   `enrich.options.question=` and `enrich.options.model=` steer it. Install
   `channel-youtube` as well: it writes the page, and without it there is
   nothing to carry the notes.

4. **Run it**, jailed, through the runner: `{{@brain-cli-ops}} jobs run
   job=<slug> wait=<s>` harvests the video, then enriches it, then writes
   the page. `{{@brain-cli-ops}} tickets show <id>` names a failed enrich's
   reason.

5. **A smoke test before mapping the route**, from the catalog's own
   checkout, outside any wiki and at your own terminal, with a throwaway key
   in the environment of the one command:

   ```sh
   GEMINI_API_KEY=<key> python3 skills/channel-youtube-watch-gemini/scripts/watch_gemini.py --item <youtube url> --capture-dir <scratch dir>
   ```

   It prints `{"status": "ok", ...}` and leaves `watch.md` under `enrich/`.

6. Enable the skill on every OTHER machine that enriches
   (`/{{@brain-plugin}}:enable {{@brain-unit}}`) — installed is
   not loaded, and enablement never travels with a `git pull`.

Unverified: the jailed run, where the proxy spends the key through the
route, has not been exercised against the live API.
