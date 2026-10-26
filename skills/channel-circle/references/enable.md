# channel-circle — after enabling

1. **Auth walkthrough** — Circle content is licensed, so do it now:
   `{{@brain-cli-ops}} credentials set <domain> kind=dir login=browser host=<domain>`
   once, then `{{@brain-cli-ops}} credentials login <domain>` (attended, macOS only)
   opens a real Chrome window; the operator logs in (solving any Turnstile/2FA), opens a
   gated lesson to confirm access, then presses Enter in the terminal. This
   saves the storage state AND the persistent per-domain profile — on
   Circle the profile is the load-bearing half (Cloudflare's `cf_clearance`
   is fingerprint-bound to it; see the SKILL.md's Auth section).
   The credential store never syncs, so every harvesting machine repeats
   this once, and maps the profile to the job once the job exists (step 3).
2. Declare the job, naming the skill: `{{@brain-cli-ops}} jobs add
   <space-root-url> slug=<community> description="<what this is>"
   skill=channel-circle` — the skill's manifest supplies `every=once`,
   `harvest.scope=section`, `harvest.access=licensed`,
   `harvest.assets=download` and a `dest` of `sources/courses/<slug>`.
   `reference` keeps no lesson video and yields no transcript (the venue's
   only reference is a signed HLS manifest, dead within hours); `download`
   is many GB per course. Pass `harvest.assets=reference` only for a
   community whose lessons are text. Scope `section` means "under the
   job's url", so that url must be the space ROOT (`/c/<slug>`): from a
   lesson url every sibling lesson is outside it. Pass
   `harvest.scope=domain` to take the whole community. A course longer than
   one 30-minute slice ends `partial`, and an `every=once` job is never
   pulled again by itself: re-queue it with `{{@brain-cli-ops}} tickets
   retry <id>` (three attempts per ticket), or declare a period
   (`every=1d`) until the course is held — each run skips what it already has.
3. **Map the profile to the job**, on each machine that harvests:
   `{{@brain-cli-ops}} credentials bind job <slug> dir=<domain>`. The slice is then
   granted that directory read-write, and the ticket names it as
   `credential_dir`. The manifest declares the slot `"required"`, so a
   machine that maps nothing claims none of the job's harvests: `jobs claim`
   refuses, "harvest requires dir and this machine fills none of it". Bind the
   job, not the skill: a skill's `dir` is handed to every job of the skill,
   unattended. `skills enable` maps nothing by itself (`/{{@brain-plugin}}:enable`
   runs it with `--confirm`, which asks no question and lists this line as
   unmapped).
