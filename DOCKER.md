# Running Project Wiki with Docker

## Prerequisites

- Docker and Docker Compose installed
- An existing Caddy installation on the host (Caddy is **not** run in Docker)

---

## Setup

### 1. Copy and fill in .env

```bash
cp .env.example .env
# Edit .env with your values
```

Set `DATA_DIR` to the absolute path of your `Project_Wiki_Data` directory.
That directory must contain `db/`, `uploads/`, and `log/` subdirectories
(created by the original `setup.sh`, or create them manually for a fresh install).

### 2. Check your MongoDB version

Run `mongod --version` on the host. If your existing version is not 3.6, update the
`image:` line in `docker-compose.yml` to match (e.g., `mongo:4.4`). Also update the
healthcheck command if using 4.x or later (replace `mongo` with `mongosh`).

### 3. Start the containers

```bash
docker compose up -d
```

The `app` container waits for MongoDB to pass its healthcheck before starting.
On first run with an existing database this may take 20-30 seconds.

### 4. Verify the app is running

```bash
curl -s http://localhost:8080 | head -5
```

You should see HTML output. If you get a connection refused, check logs:

```bash
docker compose logs app
docker compose logs mongo
```

---

## Migrating from an Existing Installation

### Before you start

1. Collect your existing credentials:
   - MongoDB username/password (set during `setup.sh`)
   - Flask `SECRET_KEY` (from your environment or the `config.py` defaults you used)
   - Admin account details

2. Verify your MongoDB version: `mongod --version`

### Migration steps

1. **Stop all existing services** (this also stops the host Caddy process —
   the wiki will be offline until Step 5):

   ```bash
   cd macosx && bash stop.sh
   ```

2. **Populate `.env`** using `.env.example` as a template, filling in your
   existing credentials. Set `DATA_DIR` to the absolute path of your
   existing `Project_Wiki_Data` directory.

3. **Start Docker services:**

   ```bash
   docker compose up -d
   ```

   MongoDB will find its existing data files in `db/` and start with `--auth`.
   The `MONGO_INITDB_*` variables are ignored when the data directory is non-empty —
   the existing users are already embedded in the data files. Your `.env` credentials
   **must** match the ones you set during the original `setup.sh` run.

4. **Update your host Caddyfile** — add a new site block:

   ```caddyfile
   wiki.example.com {
       tls /path/to/cert.pem /path/to/key.pem
       reverse_proxy localhost:8080
   }
   ```

5. **Restart Caddy:**

   ```bash
   caddy reload
   # or: sudo systemctl restart caddy
   ```

---

## Caddy Configuration

Caddy handles TLS termination with your company-provided certificates. The app
container speaks plain HTTP on port 8080 and is bound to `127.0.0.1` only.

```caddyfile
wiki.example.com {
    tls /path/to/cert.pem /path/to/key.pem
    reverse_proxy localhost:8080
}
```

---

## Backups

Both MongoDB data and file uploads are stored on the host filesystem under
`Project_Wiki_Data/`. Back up this directory with your normal backup tooling
(rsync, tar, etc.).

For crash-safe logical backups, run `mongodump` against the running container:

```bash
docker compose exec mongo mongodump \
  -u "$DB_USER" -p "$DB_PASS" --authenticationDatabase admin \
  --archive | gzip > ~/pw-backup-$(date +%Y%m%d).gz
```

---

## Common Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f app
docker compose logs -f mongo

# Restart app only (after code changes)
docker compose build app && docker compose up -d app

# Open a shell in the app container
docker compose exec app bash
```
