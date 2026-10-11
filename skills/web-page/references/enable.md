# web-page — after enabling

1. A plain-url job names this unit as its harvester, the way a channel
   unit's job names its own — `jobs add` picks no unit for a url on its own:

   ```sh
   llm-wiki-ops jobs add <url> slug=<slug> description="<what this is>" skill=web-page
   ```

2. `jobs ls` and, for any job still naming the old
   `llm-wiki:harvest-page` skill, repoint it:

   ```sh
   llm-wiki-ops jobs edit <slug> harvest.skill=web-page
   ```
