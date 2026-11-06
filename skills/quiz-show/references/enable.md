# quiz-show — after enabling

1. Run a first show by hand and read it:

   ```sh
   /quiz-show
   ```

   It writes the episode under `wiki/podcasts/` and says where it put it.
   The script is in the page: read it, and edit a line. Once the audio is
   made, an edit takes `{{@brain-cli-ops}} page edit "<episode>"
   audio_refresh=podcast` to make it again. The show finds weak spots in what `/{{@brain-plugin}}:quiz` logs,
   so it is review only until the learner has taken a quiz.

2. Give the hosts voices. The episode asks for its audio with
   `audio: podcast`; the plugin's `narrate` engine renders it on a machine
   that has one, and the wiki's `[narrate.voices]` maps each host's name
   (`Alex`, `Sam`, or the names your `quiz-show` overlay gives them) to a
   voice. A name nobody mapped takes the next of `[narrate] default_voices`.
   `{{@brain-cli-ops}} doctor` says whether this machine can narrate.

3. To get a show every day, declare a job. It runs this unit as its
   routine, on the weak spots of the newest quiz sessions:

   ```sh
   {{@brain-cli-ops}} jobs add quiz-show routines=quiz-show every=1d description="the daily audio quiz"
   ```

   A scheduled run never asks questions and never makes the audio itself:
   it writes the episode, and the host's next `narrate` pass renders it.
