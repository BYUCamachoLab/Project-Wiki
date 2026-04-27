# Dockerize Project Wiki Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Containerize Project Wiki with Docker Compose (app + MongoDB), enabling zero-copy migration from an existing installation and integration with a host Caddy instance.

**Architecture:** Two Docker services — `mongo` (bind-mounted to existing `db/`) and `app` (Flask/Waitress, bind-mounted to existing `uploads/`) — coordinated via `docker-compose.yml`. Host Caddy reverse-proxies port 8080. Minimal code changes to `config.py` make it fully env-configurable.

**Tech Stack:** Docker Compose, python:3.9-slim, mongo:3.6, Waitress 1.0.2, MongoEngine 0.13.0

---

## Chunk 1: config.py + Dockerfile + .dockerignore

### Task 1: Patch config.py for Docker compatibility

**Files:**
- Modify: `config.py`

Three changes are needed: cast `DB_PORT` to `int` (env vars are always strings; MongoEngine requires an integer), and make `MAIL_SERVER`/`MAIL_PORT` read from environment variables instead of being hardcoded.

- [ ] **Step 1: Open config.py and locate the three lines to change**

  Current state of the relevant lines:
  ```python
  # Line 14 — port is a string when set from env
  'port': os.environ.get('DB_PORT', 27017),

  # Lines 25-26 — hardcoded, not configurable
  MAIL_SERVER = 'smtp.googlemail.com'
  MAIL_PORT = 587
  ```

- [ ] **Step 2: Apply the three changes**

  In `config.py`, change line 14 to:
  ```python
  'port': int(os.environ.get('DB_PORT', 27017)),
  ```

  Change lines 25–26 to:
  ```python
  MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
  MAIL_PORT    = int(os.environ.get('MAIL_PORT', 587))
  ```

- [ ] **Step 3: Verify the file looks correct**

  Run:
  ```bash
  grep -n "port.*environ\|MAIL_SERVER\|MAIL_PORT" config.py
  ```

  Expected output (line numbers may shift slightly):
  ```
  14:        'port': int(os.environ.get('DB_PORT', 27017)),
  25:    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.googlemail.com')
  26:    MAIL_PORT    = int(os.environ.get('MAIL_PORT', 587))
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add config.py
  git commit -m "fix: make config.py fully env-configurable for Docker"
  ```

---

### Task 2: Create .dockerignore

**Files:**
- Create: `.dockerignore`

Keeps the build context small and prevents secrets or data directories from being copied into the image. **Critical:** `macosx/requirements.txt` must NOT be excluded — the Dockerfile uses it.

- [ ] **Step 1: Create .dockerignore**

  Create `/home/sequoia/git/Project-Wiki/.dockerignore` with this content:
  ```
  # Data directories — never in the image
  Project_Wiki_Data/

  # Git and editor noise
  .git/
  .gitignore
  docs/

  # Python cache
  __pycache__/
  *.pyc
  *.pyo
  *.pyd

  # Secrets
  .env

  # Platform-specific scripts (keep macosx/requirements.txt — Dockerfile needs it)
  macosx/*.sh
  windows/

  # Misc
  PW_Caddyfile
  README.md
  CLAUDE.md
  LICENSE
  ```

- [ ] **Step 2: Verify macosx/requirements.txt is NOT excluded**

  Confirm the file does not appear in `.dockerignore`:
  ```bash
  grep "requirements" .dockerignore && echo "FAIL: requirements.txt will be excluded" || echo "OK: requirements.txt not excluded"
  ```

  Expected output: `OK: requirements.txt not excluded`

- [ ] **Step 3: Commit**

  ```bash
  git add .dockerignore
  git commit -m "chore: add .dockerignore for Docker build"
  ```

---

### Task 3: Create Dockerfile

**Files:**
- Create: `Dockerfile`

Builds the Flask/Waitress app image. Uses `python:3.9-slim` for compatibility with the pinned old packages. `WORKDIR /app` + `COPY . /app/` places `config.py` at `/app/config.py`, which is required for `UPLOAD_FOLDER` to resolve to `/Project_Wiki_Data/uploads` (config.py computes the path as one level above its own location).

The start command uses `from app import create_app` directly — not `from manage import app` — to avoid a flask_script dependency at serve time. Uses `host=`/`port=` separately because `waitress==1.0.2` does not support the `listen=` keyword.

- [ ] **Step 1: Create Dockerfile**

  Create `/home/sequoia/git/Project-Wiki/Dockerfile` with this content:
  ```dockerfile
  FROM python:3.9-slim

  WORKDIR /app

  # Copy everything (see .dockerignore for exclusions)
  COPY . /app/

  # Install dependencies
  RUN pip install --no-cache-dir -r macosx/requirements.txt

  EXPOSE 8080

  # Shell-form CMD so the Python one-liner doesn't need JSON-array escaping.
  # Uses 'from app import create_app' directly (not manage.py) to avoid
  # importing flask_script at serve time.
  # host= and port= used separately because waitress==1.0.2 has no listen= kwarg.
  CMD python -c "from app import create_app; from waitress import serve; app = create_app(); serve(app, host='0.0.0.0', port=8080, threads=4)"
  ```

- [ ] **Step 2: Build the image to verify it compiles**

  Run:
  ```bash
  docker build -t project-wiki:latest .
  ```

  Expected: build completes without errors. All pip packages install successfully under Python 3.9.

  Common failure: a package fails to build from source. If so, install the missing system dependency with `apt-get` in the Dockerfile before the `pip install` step (e.g., `RUN apt-get update && apt-get install -y libffi-dev`).

- [ ] **Step 3: Verify the image starts (smoke test without Mongo)**

  Validate that the startup import chain works (create_app + waitress importable):
  ```bash
  docker run --rm project-wiki:latest \
    python -c "from app import create_app; from waitress import serve; print('imports ok')"
  ```

  Expected output: `imports ok`

  Note: `create_app()` is not called here because it tries to connect to MongoDB.
  Full startup is validated in Task 7 (end-to-end verification with a live Mongo).

- [ ] **Step 4: Commit**

  ```bash
  git add Dockerfile
  git commit -m "feat: add Dockerfile for Flask/Waitress app"
  ```

---

## Chunk 2: docker-compose.yml + .env.example

### Task 4: Create .env.example

**Files:**
- Create: `.env.example`

Template for the `.env` file users copy and fill in. All variable names match exactly what `config.py` reads via `os.environ.get(...)`.

- [ ] **Step 1: Create .env.example**

  Create `/home/sequoia/git/Project-Wiki/.env.example` with this content:
  ```bash
  # Absolute path to your Project_Wiki_Data directory
  DATA_DIR=/absolute/path/to/Project_Wiki_Data

  # MongoDB — must match credentials already in your existing data files
  # (set during the original setup.sh run)
  DB_SERVICE=mongo
  DB_PORT=27017
  DB_NAME=admin
  DB_USER=your_mongo_username
  DB_PASS=your_mongo_password

  # Flask session secret — must match your existing installation's SECRET_KEY
  SECRET_KEY=change_this_to_a_long_random_string

  # Super admin account (used only if creating a fresh installation)
  ADMIN_USERNAME=admin
  ADMIN_EMAIL=admin@example.com
  ADMIN_PASSWORD=change_this_password

  # Email (optional — only needed for password reset / notifications)
  MAIL_SERVER=smtp.googlemail.com
  MAIL_PORT=587
  MAIL_USERNAME=your_email@gmail.com
  MAIL_PASSWORD=your_email_password
  ```

- [ ] **Step 2: Verify .env is in .gitignore**

  Run:
  ```bash
  grep "^\.env$" .gitignore
  ```

  If no output (`.env` not ignored), add it:
  ```bash
  echo ".env" >> .gitignore
  git add .gitignore
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add .env.example
  git commit -m "chore: add .env.example for Docker configuration"
  ```

---

### Task 5: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

Defines both services. Key details:
- `mongo` is started with `--auth` via the `command` override; without this, MongoDB starts without authentication.
- The healthcheck uses `mongo` (legacy shell), not `mongosh` — `mongosh` does not exist in `mongo:3.6`.
- `app` uses `depends_on: condition: service_healthy` so it waits for MongoDB to actually accept connections, not just for the container to start.
- Both bind mounts reference `${DATA_DIR}` from `.env`.
- The uploads bind mount target is `/Project_Wiki_Data/uploads` — matching the path `config.py` computes at runtime (one level above `/app/config.py`).
- Port `127.0.0.1:8080:8080` exposes only to localhost so host Caddy can reach it but it is not publicly exposed.

- [ ] **Step 1: Create docker-compose.yml**

  Create `/home/sequoia/git/Project-Wiki/docker-compose.yml` with this content:
  ```yaml
  services:
    mongo:
      image: mongo:3.6
      command: ["mongod", "--auth"]
      volumes:
        - ${DATA_DIR}/db:/data/db
      restart: unless-stopped
      healthcheck:
        test: ["CMD", "mongo", "--eval", "db.adminCommand('ping')"]
        interval: 10s
        timeout: 5s
        retries: 5
        start_period: 20s

    app:
      build: .
      image: project-wiki:latest
      ports:
        - "127.0.0.1:8080:8080"
      volumes:
        - ${DATA_DIR}/uploads:/Project_Wiki_Data/uploads
      environment:
        DB_SERVICE: mongo
        DB_PORT: ${DB_PORT:-27017}
        DB_NAME: ${DB_NAME:-admin}
        DB_USER: ${DB_USER}
        DB_PASS: ${DB_PASS}
        SECRET_KEY: ${SECRET_KEY}
        ADMIN_USERNAME: ${ADMIN_USERNAME:-admin}
        ADMIN_EMAIL: ${ADMIN_EMAIL}
        ADMIN_PASSWORD: ${ADMIN_PASSWORD}
        MAIL_SERVER: ${MAIL_SERVER:-smtp.googlemail.com}
        MAIL_PORT: ${MAIL_PORT:-587}
        MAIL_USERNAME: ${MAIL_USERNAME:-}
        MAIL_PASSWORD: ${MAIL_PASSWORD:-}
      depends_on:
        mongo:
          condition: service_healthy
      restart: unless-stopped
  ```

- [ ] **Step 2: Validate the compose file syntax**

  Run:
  ```bash
  docker compose config
  ```

  This will fail if `DATA_DIR` is not set. That is expected — it requires a `.env` file. To validate syntax only:
  ```bash
  docker compose config 2>&1 | grep -i "error\|invalid" || echo "Syntax OK"
  ```

  If the output contains errors unrelated to missing env vars, fix them before proceeding.

- [ ] **Step 3: Commit**

  ```bash
  git add docker-compose.yml
  git commit -m "feat: add docker-compose.yml for app + mongo services"
  ```

---

## Chunk 3: DOCKER.md + end-to-end verification

### Task 6: Create DOCKER.md

**Files:**
- Create: `DOCKER.md`

User-facing documentation covering: fresh setup, migration from an existing instance, and Caddy configuration. Written for someone who knows their existing Project Wiki setup.

- [ ] **Step 1: Create DOCKER.md**

  Write `/home/sequoia/git/Project-Wiki/DOCKER.md` using the Write tool (or equivalent) with the following content. The file contains markdown with embedded code fences, so write it directly rather than via a shell heredoc.

  File contents:

      # Running Project Wiki with Docker

      ## Prerequisites

      - Docker and Docker Compose installed
      - An existing Caddy installation on the host (Caddy is **not** run in Docker)

      ---

      ## Setup

      ### 1. Copy and fill in .env

          cp .env.example .env
          # Edit .env with your values

      Set `DATA_DIR` to the absolute path of your `Project_Wiki_Data` directory.

      ### 2. Check your MongoDB version

      Run `mongod --version` on the host. If your existing version is not 3.6, update the
      `image:` line in `docker-compose.yml` to match (e.g., `mongo:4.4`). Also update the
      healthcheck command if using 4.x or later (replace `mongo` with `mongosh`).

      ### 3. Start the containers

          docker compose up -d

      The `app` container waits for MongoDB to pass its healthcheck before starting.
      On first run with an existing database this may take 20-30 seconds.

      ### 4. Verify the app is running

          curl -s http://localhost:8080 | head -5

      You should see HTML output. If you get a connection refused, check logs:

          docker compose logs app
          docker compose logs mongo

      ---

      ## Migrating from an Existing Installation

      ### Before you start

      1. Collect your existing credentials:
         - MongoDB username/password (set during `setup.sh`)
         - Flask `SECRET_KEY` (from your environment or `config.py` defaults)
         - Admin account details

      2. Verify your MongoDB version: `mongod --version`

      ### Migration steps

      1. **Stop all existing services** (this also stops the host Caddy process —
         the wiki will be offline until Step 5):

             cd macosx && bash stop.sh

      2. **Populate `.env`** using `.env.example` as a template, filling in your
         existing credentials. Set `DATA_DIR` to the absolute path of your
         existing `Project_Wiki_Data` directory.

      3. **Start Docker services:**

             docker compose up -d

         MongoDB will find its existing data files in `db/` and start with `--auth`.
         The `MONGO_INITDB_*` variables are ignored when the data directory is non-empty —
         the existing users are already embedded in the data files. Your `.env` credentials
         **must** match the ones you set during the original `setup.sh` run.

      4. **Update your host Caddyfile** — add a new site block:

             wiki.example.com {
                 tls /path/to/cert.pem /path/to/key.pem
                 reverse_proxy localhost:8080
             }

      5. **Restart Caddy:**

             caddy reload
             # or: sudo systemctl restart caddy

      ---

      ## Caddy Configuration

      Caddy handles TLS termination with your company-provided certificates. The app
      container speaks plain HTTP on port 8080 and is bound to `127.0.0.1` only.

          wiki.example.com {
              tls /path/to/cert.pem /path/to/key.pem
              reverse_proxy localhost:8080
          }

      ---

      ## Backups

      Both MongoDB data and file uploads are stored on the host filesystem under
      `Project_Wiki_Data/`. Back up this directory with your normal backup tooling
      (rsync, tar, etc.).

      For crash-safe logical backups, run `mongodump` against the running container:

          docker compose exec mongo mongodump \
            -u "$DB_USER" -p "$DB_PASS" --authenticationDatabase admin \
            --archive | gzip > ~/pw-backup-$(date +%Y%m%d).gz

      ---

      ## Common Commands

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

- [ ] **Step 2: Commit**

  ```bash
  git add DOCKER.md
  git commit -m "docs: add DOCKER.md with setup and migration instructions"
  ```

---

### Task 7: End-to-end verification

This task uses an empty temporary data directory to confirm the full stack starts and the app is reachable. Because MongoDB starts with `--auth` and `MONGO_INITDB_*` variables are only honoured on empty data directories, the test creates a MongoDB root user before starting the app.

- [ ] **Step 1: Create a test .env and empty data directories**

  ```bash
  mkdir -p /tmp/pw-test/db /tmp/pw-test/uploads
  cat > /tmp/pw-test.env << 'EOF'
  DATA_DIR=/tmp/pw-test
  DB_SERVICE=mongo
  DB_PORT=27017
  DB_NAME=admin
  DB_USER=testuser
  DB_PASS=testpass
  SECRET_KEY=testsecretkey
  ADMIN_USERNAME=admin
  ADMIN_EMAIL=admin@example.com
  ADMIN_PASSWORD=adminpass
  EOF
  ```

- [ ] **Step 2: Start mongo alone and create the root user**

  Start only the `mongo` service, then poll until healthy, then create the user:
  ```bash
  docker compose --env-file /tmp/pw-test.env up -d mongo

  # Wait for mongo to be ready (healthcheck start_period is 20s)
  echo "Waiting for mongo to be healthy..."
  until docker compose --env-file /tmp/pw-test.env exec mongo \
    mongo --quiet --eval "db.adminCommand('ping').ok" 2>/dev/null | grep -q "^1$"; do
    sleep 3
  done
  echo "Mongo ready."

  docker compose --env-file /tmp/pw-test.env exec mongo \
    mongo admin --eval \
    "db.createUser({user:'testuser',pwd:'testpass',roles:[{role:'root',db:'admin'}]})"
  ```

  Expected: final output ends with `{ "ok" : 1 }`.

- [ ] **Step 3: Start the app container**

  ```bash
  docker compose --env-file /tmp/pw-test.env up -d app
  ```

  Wait for the app to start (the healthcheck on mongo is already passing):
  ```bash
  docker compose --env-file /tmp/pw-test.env ps
  ```

  Expected: both `mongo` and `app` show `running`.

- [ ] **Step 4: Confirm the app responds**

  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
  ```

  Expected: `200` or `302` (redirect to login page). Any 5xx or connection refused means the app failed — check logs:
  ```bash
  docker compose --env-file /tmp/pw-test.env logs app
  ```

- [ ] **Step 5: Tear down the test stack**

  ```bash
  docker compose --env-file /tmp/pw-test.env down
  rm -rf /tmp/pw-test /tmp/pw-test.env
  ```

- [ ] **Step 6: Final commit and summary**

  All files are already committed. Run:
  ```bash
  git log --oneline -6
  ```

  Expected commits (most recent first):
  ```
  <hash>  docs: add DOCKER.md with setup and migration instructions
  <hash>  feat: add docker-compose.yml for app + mongo services
  <hash>  chore: add .env.example for Docker configuration
  <hash>  feat: add Dockerfile for Flask/Waitress app
  <hash>  chore: add .dockerignore for Docker build
  <hash>  fix: make config.py fully env-configurable for Docker
  ```
