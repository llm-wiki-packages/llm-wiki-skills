#!/bin/sh
# `ntn` as the harness's PATH has it, so `skills enable` records this file as
# the unit's bin and the sandbox's `probe` runs it: `whoami`
# answers offline, and only where the route reached the jail — its variable
# holds the proxy's phantom. `--version` is the real ntn's, which `skills
# enable` reads. Any other call is refused: nothing in this suite reaches
# Notion.
here="$(cd "$(dirname "$0")" && pwd)"
case "${1:-}" in
    whoami)
        [ -n "${NOTION_API_TOKEN:-}" ] || { echo "ntn: NOTION_API_TOKEN is unset: the notion route did not reach this jail" >&2; exit 1; }
        echo '{"bot": {"workspace_name": "harness"}}'
        exit 0
        ;;
    --version)
        real="$(PATH="$(printf '%s' "$PATH" | tr ':' '\n' | grep -vxF "$here" | paste -sd: -)" command -v ntn)"
        [ -n "$real" ] || { echo "ntn: not installed" >&2; exit 127; }
        exec "$real" --version
        ;;
esac
echo "ntn (harness): refused $*" >&2
exit 2
