# channel-frameio — after enabling

1. Check Playwright's Chromium build is installed on the harvesting machine
   (`uvx playwright install chromium`, outside any jail: the slice reads it
   from `playwright-cache` and can never write it) — a worker that cannot
   launch it captures nothing; tell the operator if it is missing. The process step needs neither: it reads the bytes harvest left
   and writes the page.
2. No auth walkthrough: guest share links authorize themselves.
3. Declare the job, naming the skill: `{{@brain-cli-ops}} jobs add
   <share-url> slug=<content-name>
   description="<what this is>" skill=channel-frameio
   dest=sources/scrapes/<content-name>` — the skill's manifest supplies
   `every=once`, `harvest.scope=domain` and `harvest.assets=download`.
   `reference` keeps no video and yields no transcript (the venue's only
   reference is a signed URL, dead within hours); `download` is many GB per
   share. Pass `harvest.assets=reference` only to take a share's documents
   and none of its media. **Scope MUST stay `domain`**: a
   share's leaves sit under the share host, not under the watched URL, so
   `page` and (for a FOLDER inside the share) `section` both exclude them.
   Name `dest` for the content now. To move it later, move the job with its
   folder: `{{@brain-cli-ops}} jobs edit <slug> dest=<new> --move-folder`,
   then re-run the command it prints with `--confirm`.
   `dest` is also the one directory the skill's process step writes: it is
   handed to the page builder verbatim, off each process ticket.
