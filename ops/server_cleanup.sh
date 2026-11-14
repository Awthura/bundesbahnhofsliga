#!/usr/bin/env bash
# Retention on the storage server. Run daily from root's crontab:
#   15 4 * * *  /srv/bbl/server_cleanup.sh >> /var/log/bbl_cleanup.log 2>&1
# Raw collector dumps are big and only needed until the day is final, so keep them briefly.
# Per-day stops are small (about 200 KB per day) and are the long-term archive.
set -euo pipefail
BASE=/srv/bbl/data
RAW_DAYS=${RAW_DAYS:-7}
STOPS_DAYS=${STOPS_DAYS:-800}
MAX_GB=${MAX_GB:-5}

find "$BASE/collector" -type f -name '*.parquet' -mtime +"$RAW_DAYS" -delete 2>/dev/null || true
find "$BASE/stops" -type f -name '*.parquet' -mtime +"$STOPS_DAYS" -delete 2>/dev/null || true
find "$BASE" -type f \( -name '*.part' -o -name '.*.??????' \) -mmin +120 -delete 2>/dev/null || true  # broken rsync temp files

# hard cap: if the folder still grows past MAX_GB, drop the oldest raw dumps first
while [ "$(du -s --block-size=1G "$BASE" | cut -f1)" -gt "$MAX_GB" ]; do
  oldest=$(find "$BASE/collector" -type f -name '*.parquet' -printf '%T@ %p\n' 2>/dev/null | sort -n | head -1 | cut -d' ' -f2-)
  [ -z "$oldest" ] && break
  rm -f -- "$oldest"
done
echo "$(date -Is) cleanup done, $(du -sh "$BASE" | cut -f1) used"
