# {{@brain-unit}} — customizing this skill

Most institutions serve Blackboard on their own domain
(`learn.example.edu`), not `*.blackboard.com`. Record the institution's host
in the installed SKILL.md under a "Sites" heading, and add `host:<domain>`
to the installed copy's `manifest.json` `keywords`, so `{{@brain-cli-ops}}
skills search <domain>` answers from the wiki's copy.

## Per job

- `options.timezone`: the IANA zone due dates and post times read in.
- `options.files`: `download` (the default) or `skip`.
- `options.layout`, `options.prefix`, `options.backfill`,
  `options.announcements_dir`, `options.discussions_dir`: where pages go and
  which re-render; the wiki's own choice is the installed copy's
  `watch.defaults.options` (`references/layout.md`).
- `extract.options.when`: `always` re-speaks a video that came with
  captions; `/{{@brain-plugin}}:add` changes it.
- `options.sso`: the SAML provider (`apId`, such as `_4405_1`) that an
  expired session is renewed through. Some sites' `/ultra` lands on Learn's
  own sign-in page, with one button per identity provider, rather than
  redirecting. The skill then follows that page's SAML link, and a live
  identity-provider session signs Learn in with no prompt. A page with one
  link needs no option. A page with several (students and staff, say) needs
  the one the person clicks: it is the `apId=` in that button's link.
  The keepalive check below passes it to `bb.py whoami` too.

## Staying signed in (keepalive)

The manifest declares one keepalive target, `blackboard`. On a machine
whose runner polls the wiki, the tick visits `/ultra/course` on the
credential's host inside Learn's 3 h idle timeout, and runs
`scripts/bb.py whoami --site={origin} --sso={sso?}` in the harvest jail.
The script's exit decides: 0 passes (and renews the session through SSO
where it had lapsed), 2 means the session is gone, so the course jobs are
skipped and the person is asked to run `credentials login` again. Exit 2
is only what the site or the identity provider said. A sign-in page that
never arrived, for example one a firewall held for approval, exits 4: the
keepalive records an error and blocks nothing. The renewal never waits
for a page's `load` event, so a third-party host held for approval does
not stall it.
`{origin}` is the credential's host. `--sso` is dropped where no job sets
`options.sso`, and every job on the credential must agree on it.
`{{@brain-cli-ops}} credentials info <credential>` shows the target's last
result. A wiki whose Learn times out sooner sets a shorter `idle_timeout`
in its installed copy.

## Sandbox

The manifest's `sandbox_ref` is `llm-wiki-packages/llm-wiki-skills:blackboard`.
What the stage reaches, and why:

```sh
{{@brain-cli-ops}} reference llm-wiki-packages/llm-wiki-skills:sandboxes/blackboard.md
```

The institution's own host is the job's target and joins the harvest
slice's egress at dispatch, so it needs no entry there.
