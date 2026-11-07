# podcast — after enabling

1. Run a first episode by hand and read it:

   ```sh
   /podcast this week's lectures
   ```

   It writes the episode under `wiki/podcasts/` and says where it put it.
   The script is in the page: read it, and edit a line you would say
   differently. Once the audio is made, an edit takes
   `{{@brain-cli-ops}} page edit "<episode>" narrate.refresh=podcast` to make it again.

2. Give the hosts voices. The episode asks for its audio with
   `narrate: {modes: podcast}`; the plugin's `narrate` engine renders it on a machine
   that has one, and the wiki's `[narrate.voices]` maps each host's name
   (`Alex`, `Sam`, or the names your `podcast` overlay gives them) to a
   voice. A name nobody mapped takes the next of `[narrate] default_voices`.
   `{{@brain-cli-ops}} doctor` says whether this machine can narrate.

3. To get an episode every week, declare a job. It runs this unit as its
   routine and covers what changed in `sources/` since the last episode:

   ```sh
   {{@brain-cli-ops}} jobs add podcast routines=podcast every=7d description="the weekly podcast"
   ```

   A scheduled run never asks questions and never makes the audio itself:
   it writes the episode, and the host's next `narrate` pass renders it.
