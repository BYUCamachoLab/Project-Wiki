# Page Tree Navigation — Design Spec
**Date:** 2026-03-15
**Project:** Project Wiki (`/home/sequoia/git/Project-Wiki`)
**Status:** Approved

---

## Problem

Wiki pages are flat and unstructured. Deleting a link from a page causes the linked page to "disappear" — it becomes unreachable with no navigation path. There is no way to understand the overall shape of a wiki at a glance, and no way to give pages an explicit place in a hierarchy.

## Goal

Introduce a hierarchical page tree that gives every page a permanent home in the navigation, accessible from every page in a persistent left sidebar. Add a drag-and-drop Structure settings page for admins to manage the hierarchy. Move the Table of Contents to a right sidebar. Add "Changes" and "Structure" links to the Wiki nav menu.

---

## Decisions Summary

| Question | Decision |
|---|---|
| Tree storage | Single `WikiPageTree` document per group (Approach B) |
| Orphaned pages | Shown in "Orphans" section at bottom of tree |
| Tree depth | Unlimited nesting |
| Structure permissions | Admins only |
| New page placement | Child of currently-viewed page |
| Migration depth | Full BFS from Home link graph |
| Layout | Three-column: left tree + content + right TOC, both sidebars collapsible |
| SortableJS | Served from `app/static/js/` (self-contained) |

---

## 1. Data Model

### New: `WikiPageTree` (`app/models.py`)

```python
class WikiPageTree(Document):
    tree = ListField()     # nested [{id: str, children: [...]}, ...]
    orphans = ListField()  # flat list of page id strings
    meta = {'collection': 'wiki_page_tree'}
```

- One document per group, stored in the group's own MongoDB database
- **No hardcoded `db_alias`** — accessed via `switch_db(WikiPageTree, group)` everywhere, consistent with all other group-scoped models. No pre-registration in `app/__init__.py` is needed; `switch_db` is sufficient.
- In views.py context, `group` is the URL string parameter (already `name_no_whitespace`). In `manage.py` context (iterating `WikiGroup` objects), use `group.name_no_whitespace` explicitly.
- `tree`: nested list of plain dicts `{"id": "<ObjectId str>", "children": [...]}`
- `orphans`: flat list of page id strings (no hierarchy)
- **Titles are NOT stored in tree nodes** — they are resolved at render time via a bulk lookup (see Section 7)
- The Home page is the implicit root and is **not** a node in the tree
- The entire document is replaced atomically on every save

### `WikiPage` — no changes to the model

The existing `refs` field (list of page references) is used only by the migration. The tree is the authoritative hierarchy going forward.

### `WikiCache` — model unchanged; all writes preserved

`WikiCache.add_changed_page()` is called inside `WikiPage.update_content()` (models.py ~line 262) and title data is updated in `WikiPage.rename()` (~line 290). These writes must be preserved — `wiki_show_changes` depends on `WikiCache.changes_id_title` being current. The `WikiCache` model and its model-level write calls are **not modified** by this feature.

---

## 2. Migration

**Command:** `python manage.py migrate_page_tree`

**Execution context:** Runs inside the Flask app context (provided by `flask_script` `Manager`), so all per-group DB connections registered in `app/__init__.py` at startup are available. Enumerate groups with `WikiGroup.objects.all()` (default DB), then use `switch_db(WikiPageTree, group.name_no_whitespace)` for each group.

**Algorithm (per group):**
1. Skip if `WikiPageTree` already exists for this group (idempotent; use `--force` to re-seed)
2. Load the Home page; start BFS with Home's `refs` as the initial frontier
3. Home's direct refs → top-level tree nodes; each page's `refs` → its children (first-visit wins)
4. Track a visited set (of page id strings) to handle circular links (A → B → A)
5. **None guard:** Filter `None` entries from `page.refs` before iterating: `[r for r in page.refs if r is not None]`
6. All pages not visited → `orphans`
7. Save `WikiPageTree` via `switch_db(WikiPageTree, group.name_no_whitespace)`

**Edge cases:**
- Group has no Home page → skip with printed warning
- `[[Title]]`-created pages with no content → included normally
- Running twice → no-op (unless `--force`)

---

## 3. Layout

The base template (`app/templates/layout.html`) changes from a two-column layout to a three-column layout:

```
┌─────────────────────────────────────────────────────────┐
│  Top navbar (unchanged)                                  │
├────────────┬───────────────────────────────┬────────────┤
│ Page Tree  │  Main content                 │ TOC        │
│ ~160px     │  flex: 1                      │ ~160px     │
│ collapsible│                               │ collapsible│
│            │                               │ (hidden if │
│            │                               │  no TOC)   │
└────────────┴───────────────────────────────┴────────────┘
```

**Removed from left sidebar:** Key Pages section, Changes section (with `[more]` link), `{% block tableofcontents %}`.
**Added to left sidebar:** Page Tree (rendered from `page_tree` + `page_id_title_map`).
**Added as right sidebar:** Table of Contents (rendered from `page.toc`).

**`searchform_nav`** is injected via context processor in `app/main/__init__.py:11` and is completely unaffected by changes to `wiki_render_template`.

### Left Sidebar — Page Tree

- Nested `<ul>` with `▶`/`▼` chevron toggles per node; page titles resolved from `page_id_title_map`
- Currently-viewed page highlighted (using `current_page_id`; `None` on non-page views — no highlight)
- Ancestors of current page auto-expanded on load when `current_page_id` is set
- All other expand/collapse state persisted in `localStorage` (key: `pw_tree_<group>`)
- "Orphans" section at bottom, visually dimmed (muted color), collapsible
- Collapse-all button at top of sidebar
- Sidebar-level collapse toggle (`«`/`»`) shrinks sidebar to ~32px rail; state in `localStorage` key `pw_leftsidebar_collapsed`
- **Pre-migration fallback:** When `page_tree is None`, sidebar shows a plain text note: "Page tree not yet initialized. Run `python manage.py migrate_page_tree`." — no Jinja2 iteration over None.

### Right Sidebar — Table of Contents

- Renders existing `page.toc` HTML (already stored on `WikiPage`)
- Only shown when `page.toc` is non-empty; right column hidden otherwise (no blank space)
- Existing JS that adds Bootstrap nav classes to TOC links moves here from `wiki_page.html`
- Sidebar-level collapse toggle; state in `localStorage` key `pw_rightsidebar_collapsed`

---

## 4. Structure Settings Page

All new routes are `@main.route` decorators in `app/main/views.py` (main blueprint), consistent with all other wiki routes.

**Route:** `GET /<group>/structure` (`@admin_required`)
**Save route:** `POST /<group>/structure/save` (`@admin_required`, AJAX only)

### UI

- Renders `WikiPageTree` as a nested `<ul>` using **SortableJS** (nested list plugin)
- Every `<li>` has a drag handle icon; pages can be reordered within a level or reparented by dragging into/out of a parent
- Orphans section at the bottom; pages can be dragged into or out of it
- Each node has a pencil icon for **inline rename**: clicking replaces the title with an `<input>`; on blur or Enter, sends an AJAX POST to the existing `wiki_rename_page` route (see Inline Rename below)
- "Save" button serializes the tree to JSON and POSTs to `/<group>/structure/save` via jQuery `$.ajax()` (which automatically sets `X-Requested-With: XMLHttpRequest`)
- JS shows an inline success or error notification (dismissible alert div) — no flash messages (flash requires a redirect, incompatible with AJAX save)

### Save endpoint

- Deserializes the POSTed JSON tree
- Validates all referenced page IDs exist in the group's database
- Atomically replaces the `WikiPageTree` document via `switch_db(WikiPageTree, group)`
- Returns JSON `{"ok": true}` on success or `{"error": "<message>"}` on failure

### Inline Rename

The existing `wiki_rename_page` route handles a form POST and returns a redirect. It is decorated `@user_required` (not `@admin_required`); this is correct and intentionally preserved — admins have write permission, and the Structure page is already admin-gated.

The route must be extended: detect an AJAX request via `request.headers.get('X-Requested-With') == 'XMLHttpRequest'` and return `{"ok": true, "new_title": "..."}` instead of redirecting. The non-AJAX form POST from `wiki_rename_page.html` (no `X-Requested-With` header) is preserved unchanged. The `structure.js` rename call must use jQuery `$.ajax()` to ensure the `X-Requested-With` header is set automatically.

### SortableJS

- Download `Sortable.min.js` to `app/static/js/sortable.min.js`
- Load only on the Structure page (not globally)

---

## 5. Navigation Changes

**"Wiki" dropdown menu (`app/templates/layout.html`):**

| Item | Route | Visibility |
|---|---|---|
| Cover | `/` | All |
| Home | `/<group>/home` | All |
| Changes | `/<group>/changes` | All |
| Structure | `/<group>/structure` | Admin only (`current_user.is_admin(group)`) |
| Manage | `/<group>/admin` | Admin only |
| Log out | `/logout` | All |

The existing `/<group>/changes` route (`wiki_show_changes`) is unchanged — the "Changes" menu item simply links there directly. `wiki_show_changes` does its own direct `switch_db(WikiCache, group)` fetch (views.py ~lines 95–97) and does not depend on `wiki_render_template` passing WikiCache data.

---

## 6. New Page Placement

In `app/main/views.py`, inside `wiki_page_edit`, triggered only by page save (the file-upload path `wiki_do_upload` does not trigger tree placement — out of scope):

1. Capture old refs immediately after the page fetch at line 155 (before `wiki_md()` is called): `old_ref_ids = {str(r.id) for r in page.refs if r is not None}` — the `r is not None` guard handles orphaned refs to deleted pages. (`refs` is not excluded from the `.exclude('html', 'comments')` fetch.)
2. After `wiki_md()` (line 161) AND after the raw-HTML href augmentation loop (lines 164–176) completes, `wiki_md.wiki_refs` contains the complete set of refs. Extract: `new_ref_ids = {str(r.id) for r in wiki_md.wiki_refs}`
3. `added_ids = new_ref_ids - old_ref_ids`
4. If `added_ids` is non-empty: load `WikiPageTree` once via `switch_db(WikiPageTree, group)`, find the current page's node, append all new ids as children in a single bulk operation, then save once — do not load/save per id.
5. If any added id already exists in the tree elsewhere (first-placement wins), skip it
6. If `WikiPageTree` doesn't exist yet (migration not run), skip silently

---

## 7. `wiki_render_template` changes

`app/main/views.py:24` — `wiki_render_template()`:

- **Remove entirely** the `WikiCache` fetch block (lines 25–36), including `keypages_id_title`, `changes_id_title`, and `latest_change_time`
- **Add** fetch of `WikiPageTree` via `switch_db(WikiPageTree, group)` (returns `None` if not yet migrated)
- **Add** bulk title lookup when `page_tree` is not `None`: collect all ids from `tree` and `orphans`, run `WikiPage.objects(id__in=all_ids).only('id', 'title')` via `switch_db(WikiPage, group)`, build `page_id_title_map: dict[str, str]`; pass `{}` when `page_tree is None`
- **Pass** `page_tree`, `page_id_title_map`, and `current_page_id` (default `None` — callers pass it explicitly for page views) to every template

**`current_page_id` on non-page views** (Changes, Search, Structure, etc.): callers pass `current_page_id=None`. The template and `page-tree.js` handle `None` gracefully — no page is highlighted and no auto-expansion occurs.

**`wiki_keypage_edit`** — route and template are **preserved unchanged**. The route fetches its own `WikiCache` data for the form textarea (this is separate from `wiki_render_template`'s removed WikiCache fetch). The Key Pages admin UI continues to work; it's just no longer surfaced in the sidebar. The `wiki_keypage_edit.html` template passes only `form` to `wiki_render_template` and has no dependency on `keypages_id_title` being in the template context.

**Template audit — changes to `layout.html` (lines 64–82):**
- Remove Key Pages section (`keypages_id_title` loop)
- Remove Changes section (`changes_id_title` loop, `latest_change_time`, `[more]` link)
- Remove `{% block tableofcontents %}` from left sidebar
- Add Page Tree HTML using `page_tree` + `page_id_title_map` with pre-migration fallback
- Add right TOC sidebar column

**Other templates:** `wiki_changes.html` uses only `changed_pages` and `group` — no WikiCache variables, no changes needed. All other templates extending `layout.html` reference `keypages_id_title`/`changes_id_title` only via the sidebar in `layout.html`, not in their own content blocks — confirm during implementation.

---

## 8. Page Deletion Tree Cleanup

In `app/admin/views.py`, the `delete-wikipage` handler currently removes page references from other pages' `refs` fields. Extend it to also:
- Load `WikiPageTree` via `switch_db(WikiPageTree, group)`
- Remove the deleted page's id from `tree` (recursively walk nodes) and from `orphans`
- Save the updated `WikiPageTree`

---

## 9. Files to Create / Modify

| File | Change |
|---|---|
| `app/models.py` | Add `WikiPageTree` document |
| `app/main/views.py` | Update `wiki_render_template` (fetch tree + title map, remove WikiCache fetch), `wiki_page_edit` (new page tree insertion after line 178), `wiki_rename_page` (add AJAX response mode), add `/<group>/structure` GET and `/<group>/structure/save` POST routes |
| `app/admin/views.py` | Extend `delete-wikipage` handler to remove deleted page from `WikiPageTree` |
| `app/templates/layout.html` | Three-column layout, updated Wiki nav menu, left sidebar → page tree with pre-migration fallback, right sidebar → TOC; remove `keypages_id_title`/`changes_id_title`/`latest_change_time` references |
| `app/templates/wiki_page.html` | Remove TOC block from left sidebar (now in right sidebar) |
| `app/templates/structure.html` | New template for Structure settings page (flat in `app/templates/`, no `main/` subdir) |
| `app/static/js/sortable.min.js` | Download SortableJS |
| `app/static/js/page-tree.js` | New: tree expand/collapse, localStorage, sidebar collapse toggles, handle `current_page_id=null` |
| `app/static/js/structure.js` | New: SortableJS init, tree serialization, jQuery `$.ajax()` save, inline rename via jQuery `$.ajax()` |
| `app/static/css/layout.css` (or inline `<style>` in layout.html) | Three-column layout, sidebar collapse styles, tree node styles |
| `manage.py` | Add `migrate_page_tree` command |

---

## 10. Verification

1. **Migration:** Run `python manage.py migrate_page_tree`. Check that `WikiPageTree` is created in MongoDB for each group. Verify Home's linked pages appear as top-level nodes. Verify orphaned pages appear in `orphans`.
2. **Pre-migration fallback:** View any wiki page before running migration — sidebar shows the fallback text, no Python errors.
3. **Page tree sidebar:** Load any wiki page. Confirm tree renders with correct hierarchy and page titles. Confirm current page is highlighted. Expand/collapse nodes, reload — confirm state persists.
4. **Non-page views (Changes, Search):** Confirm tree renders with no page highlighted.
5. **Sidebar collapse:** Click `«` on left sidebar — confirm it collapses to rail. Reload — confirm state persists. Same for right sidebar.
6. **TOC right sidebar:** View a page with headings — TOC appears on right. View a page without headings — right sidebar is hidden.
7. **Structure page:** Navigate to Wiki → Structure as admin. Drag a page to a new position. Click Save — confirm inline success notification appears. Reload the page tree — confirm the change persisted. Drag a page into Orphans and Save. Confirm it appears there.
8. **Inline rename:** On the Structure page, click the pencil on a page, type a new name, press Enter. Confirm the title updates in the tree sidebar on next page load.
9. **New page placement:** Edit a page and add `[[New Page Name]]`. Save. Confirm the new page appears as a child of the edited page in the tree.
10. **Navigation menu:** Confirm "Changes" link works for all users. Confirm "Structure" link is visible only to admins.
11. **Non-admin access:** Confirm `/<group>/structure` redirects non-admin users to the login page (consistent with `admin_required` — redirects, does not return 403).
12. **WikiCache still updated:** Edit a page and save. Navigate to Changes — confirm the page appears in the recent changes list.
13. **Page deletion cleanup:** Delete a page via admin panel. Confirm its node is removed from the page tree sidebar.
