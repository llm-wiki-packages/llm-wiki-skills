#!/bin/sh
# `gws` as the harness's PATH has it, so `skills enable` records this file as
# the unit's bin and the harvest stage's jail runs it. It answers only out of
# the login directory the job's `dir` slot granted — `getProfile`, `messages
# list` and `messages get`, each a file there — so a run that reaches it at
# all proves the grant reached the jail. `--version` is the real gws's, which
# `skills enable` reads. Anything else is refused: nothing in this suite
# reaches Google.
here="$(cd "$(dirname "$0")" && pwd)"
if [ "${1:-}" = "--version" ]; then
    real="$(PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$here" | paste -sd: -)" command -v gws)"
    [ -n "$real" ] && exec "$real" --version
    echo "gws 0.22.5"
    exit 0
fi
dir="${GOOGLE_WORKSPACE_CLI_CONFIG_DIR:-}"
[ -n "$dir" ] && [ -d "$dir" ] || { echo "gws (harness): no login directory: the dir slot did not reach this jail" >&2; exit 2; }
[ "${GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND:-}" = "file" ] || { echo "gws (harness): the keyring backend is not file" >&2; exit 2; }
case "$1 $2 $3 ${4:-}" in
    "gmail users getProfile --params")
        exec cat "$dir/profile.json"
        ;;
    "gmail users messages list")
        exec cat "$dir/list.json"
        ;;
    "gmail users messages get")
        id="$(printf '%s' "$6" | sed -n 's/.*"id": *"\([A-Za-z0-9]*\)".*/\1/p')"
        [ -f "$dir/msg-$id.json" ] || { echo "gws (harness): no message $id" >&2; exit 1; }
        exec cat "$dir/msg-$id.json"
        ;;
esac
echo "gws (harness): refused $*" >&2
exit 3
