# Storage server setup (Hetzner)

The server is only an archive: GitHub Actions pushes compact per-day stops (`stops/*.parquet`),
`daily_points.csv`, and (if enabled) raw output of our own DB API collector. The website never talks
to the server, and the server never needs credentials for anything.

Because the same machine also runs other things (a VPN), the key GitHub uses is locked down hard:
its own Unix user, no password, no shell, and the key can only run `rrsync` inside one folder.
If the key ever leaks, the worst case is someone writing files into `/srv/bbl`.

## One-time setup (as root on the server)

```sh
apt-get install -y rsync                       # rrsync ships with rsync (Debian/Ubuntu)
adduser --system --group --home /srv/bbl --shell /usr/sbin/nologin bbl
mkdir -p /srv/bbl/data /srv/bbl/.ssh
chown -R bbl:bbl /srv/bbl && chmod 700 /srv/bbl/.ssh

# Paste the public key from the GitHub setup step below, restricted to rrsync in /srv/bbl/data:
echo 'command="/usr/bin/rrsync /srv/bbl/data",restrict ssh-ed25519 AAAA...your-public-key... bbl-github-actions' \
  > /srv/bbl/.ssh/authorized_keys
chown bbl:bbl /srv/bbl/.ssh/authorized_keys && chmod 600 /srv/bbl/.ssh/authorized_keys
```

(On some distros rrsync is at `/usr/share/doc/rsync/scripts/rrsync`; check with `which rrsync`.)
Make sure `PasswordAuthentication no` is set in `/etc/ssh/sshd_config`, which it should already be on a VPN box.

## GitHub secrets (repo Settings, Secrets and variables, Actions)

| Secret | Value |
|---|---|
| `HETZNER_HOST` | server IP or hostname |
| `HETZNER_USER` | `bbl` |
| `HETZNER_SSH_KEY` | private key of a key pair made only for this (already set if Claude set it up) |
| `HETZNER_KNOWN_HOSTS` | output of `ssh-keyscan -t ed25519 <host>` run from your laptop (pins the host key) |
| `DB_CLIENT_ID`, `DB_API_KEY` | optional, DB API Marketplace Timetables app, enables our own collector |

Secrets are never printed in logs and are not given to workflows triggered from forks.
Never commit keys or `.env` files; `.gitignore` blocks the usual names.

Test from your laptop: `rsync -av -e "ssh -i <private key>" bbl@<host>:` should list the folder, and
`ssh -i <private key> bbl@<host>` should refuse a shell.

## Cleanup and retention

Copy `ops/server_cleanup.sh` to `/srv/bbl/server_cleanup.sh` (owned by root, not writable by `bbl`) and add it
to root's crontab as shown at the top of the script. Defaults: raw collector dumps kept 7 days, per-day stops kept
800 days, and a hard cap of 5 GB for the whole folder so this project can never fill the VPN server's disk.
Override with `RAW_DAYS`, `STOPS_DAYS`, `MAX_GB` in the crontab line.
