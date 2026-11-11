# morning-brief — after enabling

The routine reads the wiki's git history (`op latest`, `op since`, `git
changed`), and `skills enable` names that read as a dangerous line, which
the enable's one approval answers. Run the dry run, read it to the operator,
and enable once they say yes:

```sh
{{@brain-cli-ops}} skills enable morning-brief
```

1. Run the interview once, with a person answering, so the brief is this
   wiki's own:

   ```sh
   /morning-brief setup
   ```

   It personalizes `wiki/reports/_template.html`, folds the section plan and
   tone into the `morning-brief` overlay, and retires the `morning-brief-setup`
   marker where the wiki's preset seeded one.

2. Run a first report and read it:

   ```sh
   /morning-brief
   ```

3. The morning job runs it once a day as its routine, once dream and
   wiki-report have each run within the day (the job's `requires`). It
   ships paused. Find the row of `jobs list --verbose` whose `routines=` names
   `morning-brief`, then resume it by its slug:

   ```sh
   {{@brain-cli-ops}} jobs list --verbose
   {{@brain-cli-ops}} jobs resume <slug>
   ```

   Dream and wiki-report run under a job of their own, which must be on too;
   `jobs list --verbose` shows each job's state and routines. A scheduled run
   never asks questions: it follows the overlay and writes what it could not
   answer into the report's open questions.
