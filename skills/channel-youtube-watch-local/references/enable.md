# channel-youtube-watch-local — after enabling

1. **The binaries**: `yt-dlp`, `ffmpeg` and `ffprobe` are checked by `skills
   enable`; `brew install yt-dlp ffmpeg` installs them on a Mac.
2. **Tell the operator what happens.** Nothing is sent to a model vendor's
   video service: this machine fetches a low-resolution copy of the video,
   cuts stills, and the enrich session's own model reads them, under the
   harness profile's endpoints. The copy is deleted when the stills are cut,
   and the stills when the notes are sealed. A model session costs tokens in
   proportion to the frame cap.
3. **Declare the job**, naming `channel-youtube` as the skill and this unit
   as the enrich skill. An enrich unit is never a job's `skill=`: the CLI
   refuses it there once the unit is enabled:

   ```sh
   llm-wiki-ops pipeline jobs add <video-url> slug=<video-name> description="<what this is>" skill=channel-youtube enrich.skill=channel-youtube-watch-local
   ```

   An existing `channel-youtube` job gets it with `llm-wiki-ops pipeline jobs
   edit <slug> enrich.skill=channel-youtube-watch-local`. `enrich.options.question=` and
   `enrich.options.max_frames=` steer it. Install `channel-youtube` as well: it
   writes the page, and without it there is nothing to carry the notes.
4. **Both engines on one job** is not a thing: a job has one enrich unit.
   To compare the two, add the same video as two jobs under two slugs.

Unverified: the frame fetch has not run against live YouTube from this unit,
and the sandbox's host list has not been measured.
