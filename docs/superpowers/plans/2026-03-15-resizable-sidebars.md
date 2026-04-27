# Resizable Sidebars & Structure Page 500 Fix Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Structure page 500 error and make both wiki sidebars user-resizable with width persisted in localStorage.

**Architecture:** Task 1 is a 2-file bugfix — pass the CSRF token as a template variable instead of relying on the unregistered `csrf_token()` Jinja2 global. Task 2 adds absolutely-positioned drag handles to the sidebars in `layout.html` and an inline `<script>` block to handle mousedown/mousemove/mouseup drag logic and localStorage persistence.

**Tech Stack:** Python/Flask, Flask-WTF 0.14.2, Jinja2, vanilla JS (no new libraries), Bootstrap 4, jQuery 3.2.1

---

## Chunk 1: Fix Structure Page 500 Error

### Task 1: Fix `wiki_structure` view

**Files:**
- Modify: `app/main/views.py`
- Modify: `app/templates/structure.html`

- [ ] **Step 1: Add `generate_csrf` import**

  Open `app/main/views.py`. At the top of the file, add this import alongside the other Flask-WTF imports:

  ```python
  from flask_wtf.csrf import generate_csrf
  ```

- [ ] **Step 2: Pass token to template**

  In `app/main/views.py`, find this function (around line 452):

  ```python
  @main.route('/<group>/structure')
  @admin_required
  def wiki_structure(group):
      return wiki_render_template('structure.html', group=group)
  ```

  Change it to:

  ```python
  @main.route('/<group>/structure')
  @admin_required
  def wiki_structure(group):
      return wiki_render_template('structure.html', group=group,
                                  csrf_token=generate_csrf())
  ```

- [ ] **Step 3: Fix template to use the string variable**

  Open `app/templates/structure.html`. Find line 117:

  ```html
          data-csrf="{{ csrf_token() }}"></script>
  ```

  Change it to:

  ```html
          data-csrf="{{ csrf_token }}"></script>
  ```

- [ ] **Step 4: Verify the fix**

  Start the app (`python PW_run.py`). Log in as an admin. Navigate to `/<group>/structure`. Confirm:
  - Page renders without 500 error
  - The page structure editor is visible with the drag-and-drop tree
  - Browser devtools → Network tab → 200 response on page load

- [ ] **Step 5: Verify inline rename still works**

  On the Structure page, click the pencil icon (✎) next to a page name. Edit the name and press Enter. Confirm the rename succeeds (no 400/403 in Network tab). This verifies `generate_csrf()` stored the token in the session and `RenameForm.validate_on_submit()` accepted it.

- [ ] **Step 6: Commit**

  ```bash
  git add app/main/views.py app/templates/structure.html
  git commit -m "fix: structure page 500 — pass csrf_token via generate_csrf()"
  ```

---

## Chunk 2: Resizable Sidebars

All changes are in `app/templates/layout.html` only.

### Task 2: Add resize handle CSS

**Files:**
- Modify: `app/templates/layout.html`

- [ ] **Step 1: Add handle CSS**

  In `app/templates/layout.html`, inside the `<style>` block, append the following immediately before the `</style>` closing tag (after the existing `/* TOC */` section, around line 198):

  ```css
          /* ── Resize handles ── */
          .pw-resize-handle {
              position: absolute;
              top: 0;
              width: 6px;
              height: 100%;
              cursor: col-resize;
              z-index: 10;
          }
          .pw-resize-left  { right: 0; }
          .pw-resize-right { left: 0; }
          .pw-resize-handle:hover { background: rgba(0,0,0,0.08); }
          .pw-sidebar-left.collapsed  .pw-resize-handle,
          .pw-sidebar-right.collapsed .pw-resize-handle { pointer-events: none; }
  ```

### Task 3: Add resize handle HTML

**Files:**
- Modify: `app/templates/layout.html`

- [ ] **Step 1: Add handle to left sidebar**

  In `app/templates/layout.html`, find the following lines (lines 291–294). These close the inner content div and the `#pw-sidebar-left` div:

  ```
                  </div>
              </div>

              {# ── Main content ── #}
  ```

  Line 291 (`                </div>`, 16 spaces) closes `.pw-sidebar-left-inner`.
  Line 292 (`            </div>`, 12 spaces) closes `#pw-sidebar-left`.

  Insert the handle **between** lines 291 and 292 — i.e., as the last child of `#pw-sidebar-left`:

  ```
                  </div>
                  <div class="pw-resize-handle pw-resize-left"></div>
              </div>

              {# ── Main content ── #}
  ```

- [ ] **Step 2: Add handle to right sidebar**

  Find lines 307–309:

  ```
                  <div id="pw-toc">{{ toc_html | safe }}</div>
              </div>
          </div>
  ```

  Line 307: `                    <div id="pw-toc">` (content inside `.pw-sidebar-right-inner`)
  Line 308 (`                </div>`, 16 spaces) closes `.pw-sidebar-right-inner`.
  Line 309 (`            </div>`, 12 spaces) closes `#pw-sidebar-right`.

  Insert the handle between lines 308 and 309:

  ```
                  <div id="pw-toc">{{ toc_html | safe }}</div>
              </div>
              <div class="pw-resize-handle pw-resize-right"></div>
          </div>
  ```

### Task 4: Add resize JavaScript

**Files:**
- Modify: `app/templates/layout.html`

- [ ] **Step 1: Add inline resize script**

  Find lines 319–320:

  ```html
      <script src="{{ url_for('static', filename='js/page-tree.js') }}"></script>
      {% block scriptblock %}{% endblock %}
  ```

  Insert the new `<script>` block between them:

  ```html
      <script src="{{ url_for('static', filename='js/page-tree.js') }}"></script>
      <script>
      (function () {
          'use strict';

          var MIN_WIDTH = 120;
          var MAX_WIDTH = 450;

          var leftSidebar  = document.getElementById('pw-sidebar-left');
          var rightSidebar = document.getElementById('pw-sidebar-right');
          var leftHandle   = leftSidebar  ? leftSidebar.querySelector('.pw-resize-left')   : null;
          var rightHandle  = rightSidebar ? rightSidebar.querySelector('.pw-resize-right')  : null;
          var leftToggle   = document.getElementById('pw-left-toggle');
          var rightToggle  = document.getElementById('pw-right-toggle');

          /* ── Restore saved widths on page load ── */
          /* This script runs after page-tree.js, so .collapsed is already applied
             by the time restoreWidth runs — the check is correct. */
          function restoreWidth(sidebar, key) {
              if (!sidebar || sidebar.classList.contains('collapsed')) return;
              var saved = localStorage.getItem(key);
              if (saved) {
                  sidebar.style.width    = saved + 'px';
                  sidebar.style.minWidth = saved + 'px';
              }
          }
          restoreWidth(leftSidebar,  'pw-sidebar-left-width');
          restoreWidth(rightSidebar, 'pw-sidebar-right-width');

          /* ── Drag-to-resize ── */
          function initResize(sidebar, handle, storageKey, direction) {
              if (!handle) return;
              handle.addEventListener('mousedown', function (e) {
                  e.preventDefault();
                  var startX     = e.clientX;
                  var startWidth = sidebar.offsetWidth;

                  sidebar.style.transition       = 'none';
                  document.body.style.userSelect = 'none';

                  function onMove(e) {
                      var delta    = e.clientX - startX;
                      var newWidth = direction === 'left'
                          ? startWidth + delta
                          : startWidth - delta;
                      newWidth = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, newWidth));
                      sidebar.style.width    = newWidth + 'px';
                      sidebar.style.minWidth = newWidth + 'px';
                  }

                  function onUp() {
                      var finalWidth = parseInt(sidebar.style.width, 10);
                      if (finalWidth) {
                          localStorage.setItem(storageKey, finalWidth);
                      }
                      sidebar.style.transition       = '';
                      document.body.style.userSelect = '';
                      document.removeEventListener('mousemove', onMove);
                      document.removeEventListener('mouseup',   onUp);
                  }

                  document.addEventListener('mousemove', onMove);
                  document.addEventListener('mouseup',   onUp);
              });
          }

          initResize(leftSidebar,  leftHandle,  'pw-sidebar-left-width',  'left');
          initResize(rightSidebar, rightHandle, 'pw-sidebar-right-width', 'right');

          /* ── Restore saved width on expand ── */
          /* This script is placed AFTER page-tree.js, so page-tree.js's click handler
             fires first and has already toggled .collapsed by the time our handler runs.
             If .collapsed is now ABSENT, the sidebar was just expanded. */
          function onToggleClick(sidebar, toggleBtn, storageKey) {
              if (!sidebar || !toggleBtn) return;
              toggleBtn.addEventListener('click', function () {
                  if (sidebar.classList.contains('collapsed')) return; /* just collapsed — nothing to restore */
                  var saved = localStorage.getItem(storageKey);
                  if (!saved) return;
                  sidebar.addEventListener('transitionend', function handler() {
                      sidebar.removeEventListener('transitionend', handler);
                      sidebar.style.width    = saved + 'px';
                      sidebar.style.minWidth = saved + 'px';
                  });
              });
          }

          onToggleClick(leftSidebar,  leftToggle,  'pw-sidebar-left-width');
          onToggleClick(rightSidebar, rightToggle, 'pw-sidebar-right-width');

      }());
      </script>
      {% block scriptblock %}{% endblock %}
  ```

### Task 5: Verify and commit

- [ ] **Step 1: Verify left sidebar resize**

  Start the app. Open any wiki page. Hover over the right edge of the left sidebar — cursor should change to `↔`. Drag right to widen, drag left to narrow. Clamp at ~120px (min) and ~450px (max). Release and reload — saved width should be restored.

- [ ] **Step 2: Verify right sidebar resize**

  Navigate to a page with headings (TOC visible). Hover over the left edge of the right sidebar — cursor `↔`. Drag left to widen, drag right to narrow. Reload to confirm persistence.

- [ ] **Step 3: Verify collapse/expand preserves width**

  Resize the left sidebar to ~300px. Click «  to collapse (sidebar shrinks to 32px). Click » to expand — sidebar should restore to ~300px. No drag cursor should appear while collapsed.

- [ ] **Step 4: Verify no drag lag**

  During a drag, sidebar tracks the cursor with no visible 200ms delay (transition is suppressed). After mouseup, the transition is restored (collapse/expand is smooth again).

- [ ] **Step 5: Commit**

  ```bash
  git add app/templates/layout.html
  git commit -m "feat: resizable sidebars with localStorage persistence"
  ```
