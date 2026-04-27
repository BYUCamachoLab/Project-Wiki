# Project Wiki

A self-hosted, multi-user collaborative wiki for research teams. Inspired by the discontinued ProjectForum service, Project Wiki gives teams a private space to document work, share knowledge, and keep a full edit history — without sending data to a third-party service.

---

## Features

**Pages & editing**
- Create and edit pages with Markdown syntax and real-time preview
- Full edit history with diff view and one-click version recovery
- Page renaming that automatically updates all references

**Organization**
- Multiple isolated groups, each with its own pages, members, and uploads
- Sidebar with configurable key pages and recent changes
- Heading-based table of contents auto-generated from page content

**Collaboration**
- Comments on pages with `[@username]` mention notifications
- Full-text search across titles, content, and comments
- File uploads attachable to any page

**Access control**

| Role | Capabilities |
|------|-------------|
| Super | Everything — manages the entire installation |
| Admin | Manage users and pages within a group |
| User | Read and write pages |
| Guest | Read only |

Roles are group-specific: one account can be Admin in one group and Guest in another.

---

## Setup

### Docker (recommended)

Requires Docker and Docker Compose. Caddy (or another reverse proxy) should be running on the host to handle TLS.

```bash
cp .env.example .env
# Edit .env — set DATA_DIR, DB_USER, DB_PASS, SECRET_KEY, and admin credentials
docker compose up -d
```

For a **fresh install**, `docker compose up -d` is all you need — MongoDB will create the root user from your `.env` credentials automatically when the data directory is empty.

For **migrating an existing installation**, see [DOCKER.md](DOCKER.md).

To add the wiki to your existing Caddyfile:

```caddyfile
wiki.example.com {
    tls /path/to/cert.pem /path/to/key.pem
    reverse_proxy localhost:8080
}
```

### macOS (native)

Requires Python 3, MongoDB, and Caddy installed on the host.

```bash
cd macosx
bash setup.sh   # first-time setup: installs deps, creates DB, creates admin account
bash start.sh   # start MongoDB + Flask app + Caddy
bash stop.sh    # stop all services
```

---

## Data & Backups

All persistent data lives in `Project_Wiki_Data/`:

```
Project_Wiki_Data/
├── db/        ← MongoDB data files
├── uploads/   ← uploaded files
└── log/       ← application logs
```

To back up the entire wiki, copy this directory. To restore, point a new instance at the backup copy.

For crash-safe logical backups of the database, see the Backups section in [DOCKER.md](DOCKER.md).

---

## Customization

**Landing page image:** Replace `app/static/images/cover.jpg` with your own image (must be named `cover.jpg`).

**Email notifications:** Set `MAIL_USERNAME` and `MAIL_PASSWORD` in `.env`. The super admin's email address is used as the sender.
