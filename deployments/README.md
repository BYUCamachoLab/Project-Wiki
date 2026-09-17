# Deployment: camacholab.ee.byu.edu

## What actually runs

The wiki is a **hybrid** — containers plus one host process:

| Component | Where | Started by |
|-----------|-------|-----------|
| `project-wiki-app-1` (Waitress/Flask) | Docker | Docker, via `restart: unless-stopped` |
| `project-wiki-mongo-1` (MongoDB 8.0) | Docker | Docker, via `restart: unless-stopped` |
| Caddy (TLS + reverse proxy, :80/:443/:8443) | **Host, as root** | `camacholab-caddy.service` |

Both containers carry `restart: unless-stopped` in `docker-compose.yml`, so
**Docker brings them back at boot on its own.** The `docker compose up -d` line in
the old `autolaunch.sh` was effectively a no-op on a reboot — it only matters
after an explicit `docker compose down`.

That means the one thing `autolaunch.sh` actually accomplished at boot was
starting Caddy. `camacholab-caddy.service` replaces exactly that, and deliberately
does **not** manage the containers: coupling them would mean a Caddy restart
(to pick up a Caddyfile edit) took the whole wiki down with it.

The InvenTree stack is the proof — it has no cron entry at all and comes back
after every reboot purely on its restart policy.

## Caddy fronts four services

From `PW_Caddyfile`:

| Route | Target |
|-------|--------|
| `camacholab.ee.byu.edu/qrng*` | 127.0.0.1:8090 (`qrng.service`, QRNG_Server repo) |
| `camacholab.ee.byu.edu/music*` | 127.0.0.1:8091 (`qmusic.service`, QRNG_Server repo) |
| `camacholab.ee.byu.edu/*` | 127.0.0.1:8080 (wiki container) |
| `camacholab.ee.byu.edu:8443` | 127.0.0.1:8092 (InvenTree container) |

So this unit is the host's edge proxy, not the wiki's alone, even though the
Caddyfile lives in this repo.

## Install

```bash
sudo bash install.sh
# Stop the old cron-launched Caddy first — it holds :80/:443
sudo pkill -f 'caddy run --config PW_Caddyfile'
sudo systemctl start camacholab-caddy
```

Then remove the `@reboot ... autolaunch.sh` line from root's crontab
(`sudo crontab -e`), or both will race for the privileged ports at boot.

## Operate

```bash
systemctl status camacholab-caddy
journalctl -u camacholab-caddy -b
sudo systemctl reload camacholab-caddy   # zero-downtime Caddyfile reload
```

`ExecStartPre` runs `caddy validate`, so a Caddyfile typo fails the reload
instead of taking the front door down.

## Why not the packaged `caddy.service`?

The official apt package ships `/lib/systemd/system/caddy.service` (currently
disabled). It runs as user `caddy` against `/etc/caddy/Caddyfile`, with its
certificate store in `/var/lib/caddy`.

Caddy here runs as **root**, so its ACME certificates live in
`/root/.local/share/caddy`. Switching to the packaged unit would abandon that
store and re-issue from Let's Encrypt — a real risk for a production hostname.
This unit keeps the current user and a distinct name so it neither shadows nor
is shadowed by the packaged one.

Migrating to the packaged unit is reasonable later: it adds `ProtectSystem`,
`PrivateTmp`, and drops root via `AmbientCapabilities=CAP_NET_BIND_SERVICE`.
It needs the cert store moved to `/var/lib/caddy` and write access to
`Project_Wiki_Data/log/` for the `caddy` user. Do it as its own change.

## Bonus fix: Caddy was living in cron's cgroup

The cron-launched Caddy (`nohup caddy ... &`) stayed parented to
`/system.slice/cron.service`. Because systemd's default `KillMode` is
`control-group`, **`systemctl restart cron` — or a cron package upgrade — would
have killed Caddy**, dropping HTTPS for all four services with nothing to restart
it. Running it as its own unit removes that trap.
