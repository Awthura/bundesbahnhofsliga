#!/usr/bin/env bash
# rsync between the runner and the storage server. The server key is locked to rrsync in one folder,
# so paths here are relative to that folder (see ops/SERVER.md).
set -euo pipefail
SSH="ssh -i $HOME/.ssh/bbl_key -o StrictHostKeyChecking=yes -o BatchMode=yes"
DEST="${HETZNER_USER}@${HETZNER_HOST}"
case "${1:-}" in
  pull)            # last few days of our own collector output, for update_data.py
    mkdir -p data/collector
    INC=()
    for i in 0 1 2 3; do INC+=(--include="$(date -u -d "-$i day" +%Y-%m-%d)_*"); done
    rsync -az -e "$SSH" "${INC[@]}" --exclude='*' "$DEST:collector/" data/collector/ || true ;;
  push)            # archive: compact per-day stops and the points table
    rsync -az -e "$SSH" data/stops/ "$DEST:stops/" || true
    rsync -az -e "$SSH" data/daily_points.csv data/sources.json "$DEST:" ;;
  push-collector)
    rsync -az -e "$SSH" data/collector/ "$DEST:collector/" ;;
  *) echo "usage: sync.sh pull|push|push-collector"; exit 1 ;;
esac
