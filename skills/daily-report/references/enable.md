# daily-report — after enabling

Enabling the unit asks for `accept=.git`: the routine reads the wiki's git
history (`op latest`, `op since`, `git changed`), and `skills enable` names
that read as a dangerous line. Run the dry run, read it to the operator, and
enable with the token they type:

```sh
{{@brain-cli-ops}} skills enable daily-report accept=.git
```

1. Run the interview once, with a person answering, so the brief is this
   wiki's own:

   ```sh
   /daily-report setup
   ```

   It personalizes `wiki/reports/_template.html`, folds the section plan and
   tone into the `daily-report` overlay, and retires the `daily-report-setup`
   marker where the wiki's preset seeded one.

2. Run a first report and read it:

   ```sh
   /daily-report
   ```

3. The seeded `ops-morning` job runs it once a day as its routine, once
   dream and wiki-report have each run within the day (the job's
   `requires`). It ships paused; turn it on:

   ```sh
   {{@brain-cli-ops}} jobs resume ops-morning
   ```

   Dream and wiki-report run under a job of their own, which must be on too;
   `{{@brain-cli-ops}} jobs ls` shows each job's state. A scheduled run
   never asks questions: it follows the overlay and writes what it could not
   answer into the report's open questions.
