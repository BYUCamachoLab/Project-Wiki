# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Project Wiki is a self-hosted, multi-user collaborative wiki/documentation application (inspired by the discontinued ProjectForum service). Built with Python Flask + MongoDB, it supports multiple isolated groups (multi-tenancy) with role-based permissions.

## Running the Application

**macOS:**
```bash
cd macosx && bash setup.sh   # First-time setup: installs deps, creates DB, creates admin
cd macosx && bash start.sh   # Start MongoDB + Flask app (Waitress) + Caddy proxy
cd macosx && bash stop.sh    # Stop all services
```

**Direct Python (after setup):**
```bash
python PW_run.py             # Runs Waitress WSGI server on 127.0.0.1:8080
```

**Management:**
```bash
python manage.py create_admin   # Create a super admin account
```

**Architecture:** Caddy (port 80) → reverse proxy → Waitress/Flask (port 8080) → MongoDB (port 27017)

There are no automated tests in this project.

## Architecture

### Blueprint Structure

Three Flask blueprints, each in `app/<name>/views.py`:

- **`auth`** — Login, logout, registration, password reset
- **`main`** — Core wiki: page view/edit/history, search, file uploads, comments
- **`admin`** — Group management, user management, super-admin functions

URL pattern: `/<group_slug>/<action>` for all wiki operations.

### Multi-Tenancy

Each group has its own isolated MongoDB database. Dynamic database switching uses `mongoengine.context_managers.switch_db`. The `app/__init__.py` factory registers each group's DB connection at startup.

### Permission Model (Bit Flags)

Defined in `app/models.py` and enforced via decorators in `app/decorators.py`:

| Role | Value | Capabilities |
|------|-------|--------------|
| Super | `0xff` | Everything |
| Admin | `0x7f` | Manage groups/users, read/write |
| User | `0x03` | Read/write pages |
| Guest | `0x01` | Read only |

### Data Models (`app/models.py`)

- **`WikiUser`** — User accounts; permissions stored per group
- **`WikiGroup`** — Group definitions; each gets its own DB and upload folder
- **`WikiPage`** — Wiki pages with MongoDB full-text search index (English), version diffs, and page reference tracking
- **`WikiComment`** — Comments with `@user` notification support
- **`WikiFile`** — Uploaded file metadata
- **`WikiCache`** — Sidebar cache (key pages, recent changes)

### Markdown Pipeline

Server-side rendering uses the Python `markdown` library with `pymdown-extensions`. Client-side live preview uses `marked.js`. Utilities in `app/wiki_util/`.

### Configuration (`config.py`)

All sensitive settings are read from environment variables: `MONGODB_SETTINGS`, `SECRET_KEY`, `MAIL_*`, `SUPER_ADMIN_*`. Upload directory defaults to `Project_Wiki_Data/uploads/`.

### Static Assets

Frontend uses Bootstrap 4 + jQuery 3.2.1, stored in `app/static/`. Templates are Jinja2 in `app/templates/`.
