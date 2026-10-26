# channel-substack — after enabling

1. **Licensed newsletters need the job bound to a stored session.** The
   manifest declares `requires.credentials.file: "optional"`: a free job needs no
   binding, and a slice is granted the value only for a job bound to it.
   SKILL.md's "Auth" lists the steps — `{{@brain-cli-ops}} credentials set
   <name>`, then `{{@brain-cli-ops}} credentials bind job <slug> file=<name>` once
   the job exists. Bind the job, not the skill: a skill's `file` is handed
   to every job of the skill. `skills enable --confirm`, which
   `/{{@brain-plugin}}:enable` runs, maps nothing and lists the skill's `file` slot
   as unmapped with a `bind skill` line; leave that line unrun.
2. Declare the job, naming the skill: `{{@brain-cli-ops}} jobs add
   <archive-url> slug=<newsletter>
   description="<what this is>" skill=channel-substack
   [harvest.max_age=3m] [harvest.access=free|licensed]` — the skill's manifest
   supplies `every=1d`, `harvest.scope=domain` and a `dest` of
   `sources/newsletters/<slug>`. **Scope MUST stay `domain`**: an archive is
   every post under the newsletter's host, so never pass `harvest.scope=page`
   for this skill. `{{@brain-cli-ops}} jobs edit <slug> every=<period>` changes
   the cadence later.
