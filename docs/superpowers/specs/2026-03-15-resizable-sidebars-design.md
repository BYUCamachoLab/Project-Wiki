# Resizable Sidebars & Structure Page 500 Fix

**Date:** 2026-03-15
**Status:** Approved

## Overview

Two independent improvements to the three-column wiki layout:

1. Fix a 500 Internal Server Error on the Structure page
2. Make the left and right sidebars user-resizable, with width persisted in `localStorage`

---

## Task 1: Fix Structure Page 500 Error

### Root Cause

`app/templates/structure.html` calls `{{ csrf_token() }}` as a Jinja2 function. This global is only registered when Flask-WTF's `CSRFProtect` is initialized. The app never initializes `CSRFProtect`, so Jinja2 raises `UndefinedError: 'csrf_token' is undefined`, resulting in a 500.

The token is used only for inline renames: `structure.js` reads it from `data-csrf` on the script element and posts it as form data to `/<group>/<page_id>/rename`, which validates it through Flask-WTF's `RenameForm`.

### Fix

- In `app/main/views.py`, import `generate_csrf` from `flask_wtf.csrf` and pass the token as a plain string to the template:
  ```python
  from flask_wtf.csrf import generate_csrf

  @main.route('/<group>/structure')
  @admin_required
  def wiki_structure(group):
      return wiki_render_template('structure.html', group=group,
                                  csrf_token=generate_csrf())
  ```
- In `app/templates/structure.html`, change `{{ csrf_token() }}` to `{{ csrf_token }}` (remove the call parens, since it's now a string not a function).

No other files change. CSRF validation on the rename endpoint is handled by Flask-WTF's `FlaskForm.validate_on_submit()` independently of `CSRFProtect` — `generate_csrf()` stores the token in the session, `RenameForm` validates it on submission. This is sufficient.

---

## Task 2: Resizable Sidebars

### Scope

All changes are confined to `app/templates/layout.html`. No new files, no new dependencies.

### CSS Changes

- **No change to `position`** on the sidebars. Both already use `position: sticky`, which already establishes a containing block for absolutely-positioned children — adding `position: relative` would override `sticky` and break scroll behavior.
- Both sidebars have `overflow: hidden`. The handle must live fully within the sidebar's border box (not straddle the edge), so no change to `overflow` is needed. No `overflow` override is required.
- Add `.pw-resize-handle` styles: 6px wide, full height, absolute positioned on the outer edge of each sidebar, `cursor: col-resize`, transparent background, with a subtle hover highlight (`rgba(0,0,0,0.08)`).
- Left sidebar handle: positioned on the right edge (`right: 0`).
- Right sidebar handle: positioned on the left edge (`left: 0`).
- When a sidebar has the `.collapsed` class, set `pointer-events: none` on its handle so it can't be dragged while collapsed.

### HTML Changes

- Add `<div class="pw-resize-handle pw-resize-left"></div>` as last child of `.pw-sidebar-left`.
- Add `<div class="pw-resize-handle pw-resize-right"></div>` as last child of `.pw-sidebar-right`.

### JavaScript (inline `<script>` in layout.html)

Added inline before `{% block scriptblock %}`, after existing Bootstrap/jQuery scripts.

**On page load:**
- Read `pw-sidebar-left-width` and `pw-sidebar-right-width` from `localStorage`.
- If found and the respective sidebar is not collapsed, apply the saved value to both `width` and `min-width` of the sidebar element.

**Drag logic (shared function, parameterized by side):**
- `mousedown` on a handle: record starting `clientX` and starting sidebar width; set `sidebar.style.transition = 'none'` to prevent the 200ms CSS transition from lagging behind the cursor; attach `mousemove` and `mouseup` listeners to `document`.
- `mousemove`: let `delta = currentX - startX`. For the left sidebar: `newWidth = startWidth + delta`. For the right sidebar: `newWidth = startWidth - delta` (dragging left increases width). Clamp to `[120, 450]` px. Set `sidebar.style.width` and `sidebar.style.minWidth`.
- `mouseup`: save final width to `localStorage`; restore `sidebar.style.transition = ''`; remove `mousemove` and `mouseup` listeners. Text selection on `document.body` (disabled via `user-select: none` on `mousedown`) is restored here.

**Constants:**
- `MIN_WIDTH = 120` (px)
- `MAX_WIDTH = 450` (px)

### Behavior Notes

- Resizing is independent per sidebar (left and right each have their own `localStorage` key).
- Collapsing a sidebar after resizing preserves the saved width. On expand, the saved width is re-applied via a click listener on the toggle button. The inline resize script is placed after `page-tree.js`, so page-tree.js's click handler fires first and has already toggled `.collapsed` by the time the resize handler runs. The resize handler checks `!sidebar.classList.contains('collapsed')` — if `.collapsed` is absent, the sidebar was just expanded. It then listens for `transitionend` on the sidebar and applies the saved width once the transition completes.
- The right sidebar already hides entirely (`.empty` class) when there's no TOC — the handle is also hidden in that case since the sidebar is `display: none`.
- No interaction with the existing collapse toggle logic is needed; the handle's `pointer-events: none` when collapsed is sufficient.

---

## Files Changed

| File | Change |
|------|--------|
| `app/main/views.py` | Import `generate_csrf`; pass `csrf_token=generate_csrf()` in `wiki_structure` |
| `app/templates/structure.html` | `{{ csrf_token() }}` → `{{ csrf_token }}` |
| `app/templates/layout.html` | CSS, HTML handles, JS drag logic |
