# channel-gmail-gws — after enabling

The pipeline (a read-only login per mailbox, per pulling machine) and the
attended modes (the operator's own login, in their session) are set up
separately; either works without the other.

## The pipeline

1. **gws, and a read-only login per mailbox.** `gws --version` is 0.22.0 or
   later. Each mailbox gets its own config directory, logged in read-only
   with the file keyring backend — a jail cannot reach the macOS keychain:

   ```sh
   mkdir -p ~/.config/gws-acme-mail
   cp ~/.config/gws/client_secret.json ~/.config/gws-acme-mail/
   GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws-acme-mail GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file gws auth login --readonly -s gmail
   GOOGLE_WORKSPACE_CLI_CONFIG_DIR=~/.config/gws-acme-mail GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file gws auth status
   ```

   The OAuth client (`client_secret.json`) is the one `gws auth setup` made;
   sign in as the mailbox's account in the browser. Never log this directory
   in with `--full` or a Gmail write scope: any write scope can also send,
   and the harvest runs unattended.

2. **One watch per mailbox.** Name the target after the mailbox and reuse it
   as the slug — a wiki holds one job per target:

   ```sh
   llm-wiki-ops jobs add acme-mail slug=acme-mail skill=channel-gmail-gws description="Acme mailbox" options.mailbox=me@acme.example
   ```

   `add` asks the rest (`lookback_days`, `cap`, `exclude_labels`,
   `exclude_senders`) with their defaults; the manifest's `watch.dest` routes
   the ledgers to `research/channels/acme-mail/`.

3. **Adopt the login and bind it to the job**, on each machine that pulls —
   the directory is the credential, adopted where it stands:

   ```sh
   llm-wiki-ops credentials set gws-acme-mail kind=dir login=none path=/Users/<you>/.config/gws-acme-mail
   llm-wiki-ops credentials bind job acme-mail dir=gws-acme-mail
   ```

   `bind` refuses a name not set on this machine. A machine with no binding
   skips the job's harvest — a `bindings` doctor row, nothing fails. After a
   peer changes what the job pulls (`options.mailbox`), check the login and
   bind again. `skills enable --confirm` lists the `dir` slot as unmapped
   with a `bind skill` line: leave it unrun, a skill-wide mapping would
   answer for every mailbox.

4. **Review and bind the harvest sandbox**: `/llm-wiki:enable
   channel-gmail-gws` walks `llm-wiki-ops reference
   llm-wiki-packages/llm-wiki-skills:references/sandboxes/gmail-gws/gmail-gws.harvest.md`.
   Enable it on every other machine that pulls, too — enablement never
   travels with a `git pull`.

5. **First pull, by hand**: `llm-wiki-ops jobs claim acme-mail`, then watch
   its report. A `failed` with `auth` is the login (step 1 or 3); `denied` is
   the sandbox (step 4). That a jailed gws refreshes its token through the
   granted directory is unverified until this first run says so — report
   what it said.

6. **Run `setup`** (`/channel-gmail-gws setup`) so the process step knows the
   operator's VIPs, noise and hard rules; without a profile it judges on the
   unit's defaults.

## Attended modes

The modes run their scripts through `llm-wiki-ops run` from the operator's
session, and need a login that can create drafts and labels — the
operator's everyday one, never the pipeline's directory. Read off the
plugin's contracts, unverified by a run here: `run` from an unconfined
session composes the harvest stage's jail, which grants no login directory
at all, so the modes work where this machine runs this wiki's unit scripts
with its own logins —

```toml
# ~/.config/llm-wiki/config.toml
[unsandboxed.wikis.<key>]
units = true
```

— or from a `nono` session whose own jail grants the login directory and
the three hosts in the sandbox reference. Log that login in once
(`gws auth login -s gmail`, default directory `~/.config/gws`, or a
`GOOGLE_WORKSPACE_CLI_CONFIG_DIR` of its own) and pass it as `--config-dir`.
Smoke test, read-only: `/channel-gmail-gws triage --max 10`. Drafts test:
`/channel-gmail-gws reply --max 3`, then look in Gmail's Drafts.
