#!/bin/sh
# `parentsquare-mcp` as the harness's PATH has it, so `skills enable` records
# this file as the unit's bin. The real server is a stdio MCP server with no
# `--version`: it prints nothing a version reads from, and `skills enable`
# assumes it satisfies. This stand-in starts no server and reaches no host.
echo "parentsquare-mcp (harness): starts no server" >&2
exit 2
