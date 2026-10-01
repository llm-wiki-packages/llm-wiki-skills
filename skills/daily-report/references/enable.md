# daily-report — after enabling

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

3. The seeded `morning` bundle (a schedule) runs it once a day, after dream
   and wiki-report. Its `stages:` line reads `[/daily-report]`; see
   `llm-wiki-ops reference schedule-bundles`. A scheduled run never asks questions: it follows the
   overlay and writes what it could not answer into the report's open
   questions.
