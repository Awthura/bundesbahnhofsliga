#!/usr/bin/env bash
# Writes the deploy key and pinned host key from secrets. Never echo these.
set -euo pipefail
mkdir -p ~/.ssh && chmod 700 ~/.ssh
printf '%s\n' "$HETZNER_SSH_KEY" > ~/.ssh/bbl_key && chmod 600 ~/.ssh/bbl_key
printf '%s\n' "$HETZNER_KNOWN_HOSTS" > ~/.ssh/known_hosts && chmod 644 ~/.ssh/known_hosts
