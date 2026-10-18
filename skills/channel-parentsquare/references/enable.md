# channel-parentsquare — after enabling

Once per machine that pulls, in this order:

1. Install the server: `uv tool install parentsquare-mcp==0.4.0`. `skills enable`
   refuses until `parentsquare-mcp` is on PATH, and a slice runs the installed
   copy, never `uvx`.
2. Store the account's login, each under a name of your choosing, the value on
   stdin:
   `llm-wiki-ops credentials set parentsquare-username`
   `llm-wiki-ops credentials set parentsquare-password`
3. Bind them to the skill:
   `llm-wiki-ops credentials bind skill channel-parentsquare env.PS_USERNAME=parentsquare-username env.PS_PASSWORD=parentsquare-password`
   The bind asks how wide an `env` pair is before the yes: both values are set
   in the environment of every process in the harvest jail, and the model can
   print them. Use a login you are content for the model to hold.
4. Enable the stage's sandbox, bind the stage and enable the skill
   (`/llm-wiki:enable channel-parentsquare`). The review lists the server
   `parentsquare`, its command and the names of its `env`, and the machine
   read of the server's console script.
5. One watch per account:
   `llm-wiki-ops jobs add parentsquare slug=<slug> description="<whose account>" skill=channel-parentsquare [options.schools=<ids>] [every=1d]`
   — the target is the bare name `parentsquare`, and the manifest's
   `watch.dest` puts the daily ledgers under `research/channels/<slug>/`.

A machine that binds nothing claims no harvest: `jobs claim` refuses, naming
what the stage requires and this machine fills none of.

The server's tool directory and the Python it runs under are not granted by
the catalog (the sandbox reference's `## Machine` says why). Run the server in
the composed jail before the first pull, and end it with ctrl-D:
`llm-wiki-ops sandboxes compose skill=channel-parentsquare stage=harvest --exec -- parentsquare-mcp`.
A permission or import error means a read is missing: widen that machine's
allow file with reads of both directories.
