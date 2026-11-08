# channel-gmail-gws — the gws calls

Every Gmail call this unit makes, as the scripts make them. A session never
types one: the scripts are the interface, so a call here is for reading a
failure, not for running by hand. `gws schema gmail.<resource>.<method>`
answers any method's parameters offline.

## Logins

One login per config directory: `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` picks it
(default `~/.config/gws`), `GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file` keeps
its key beside it. `gws auth status` says who it is; `gws auth login
--readonly -s gmail` makes a read-only one. Exit codes: 0 ok, 1 API error,
2 auth error, 3 bad arguments, 4 discovery failed.

## Read (harvest and every mode)

```sh
gws gmail users getProfile --params '{"userId":"me"}'
gws gmail users messages list --params '{"userId":"me","q":"after:1789700000","maxResults":500}'
gws gmail users messages get --params '{"userId":"me","id":"<id>","format":"full"}'
gws gmail users labels list --params '{"userId":"me"}'
```

`list` answers `{messages: [{id, threadId}], nextPageToken}`, newest first.
`get` answers `internalDate` (epoch ms), `labelIds`, `snippet` and a
`payload` of headers and parts, each part's text in `body.data`,
base64url.

## Write (attended only)

```sh
gws gmail users drafts create --params '{"userId":"me"}' --json '{"message":{"raw":"<base64url RFC 822>","threadId":"<thread>"}}'
gws gmail users messages batchModify --params '{"userId":"me"}' --json '{"ids":["…"],"addLabelIds":["Label_1"],"removeLabelIds":["INBOX"]}'
gws gmail users labels create --params '{"userId":"me"}' --json '{"name":"Receipts"}'
```

System label ids: `INBOX UNREAD STARRED IMPORTANT SPAM TRASH DRAFT SENT
CATEGORY_PERSONAL CATEGORY_SOCIAL CATEGORY_PROMOTIONS CATEGORY_UPDATES
CATEGORY_FORUMS`; a user label is `Label_<n>`, resolved by name.

## Never

`+send`, `+reply`, `+reply-all`, `+forward`, `messages send`, `drafts send`,
`messages delete`, `messages trash`, `threads delete`, `threads trash`,
`settings *`, `users watch`, `users stop`.

## Query atoms

`is:unread`, `in:inbox`, `in:sent`, `newer_than:2d`, `older_than:7d`,
`after:<epoch seconds or YYYY/MM/DD>`, `from:x`, `-from:x`, `to:me`,
`-category:promotions`, `has:attachment`, `label:Waiting`, `is:starred`.
