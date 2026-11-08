# study-plan — after enabling

1. Put the syllabus in the wiki, if it is not there yet: a `playbook` page,
   by convention under `sources/playbooks/`, in whatever shape the learner
   keeps it.

   ```sh
   {{@brain-cli-ops}} page create type=playbook title="<course> syllabus" --stdin
   ```

2. Run a first plan by hand and read it:

   ```sh
   /study-plan
   ```

   It writes the guide titled `Study plan` and says where it put it.

3. A student wiki seeds the `study-plan` job, which runs this unit once a
   day as its routine, in the evening. It ships paused; turn it on:

   ```sh
   {{@brain-cli-ops}} jobs resume study-plan
   ```

   A wiki seeded from another preset has no such job. Declare one:

   ```sh
   {{@brain-cli-ops}} jobs add study-plan routines=study-plan every=1d description="the study plan"
   ```

   A scheduled run never asks questions: what it cannot settle goes into the
   plan as an open question.

The plan reads what `/{{@brain-plugin}}:quiz` logs, so it finds weak spots
only once the learner has taken a quiz.
