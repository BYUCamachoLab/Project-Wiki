# Paste and Drag-and-Drop Upload — Design Spec

**Date:** 2026-03-17
**Status:** Approved
**Scope:** Editor page only (`wiki_page_edit.html`)

## Overview

Add clipboard paste and drag-and-drop upload support to the wiki page editor. Both methods upload files immediately and insert the resulting markdown at the current cursor position, matching the behavior of the existing Upload button.

## Background

The editor page already has:
- A hidden file input and form targeting `POST /do-upload/from-edit/<group>`
- `initDropbox()` in `upload.js` which installs: (a) `#out`-scoped handlers for `dragenter`, `dragleave`, `dragover`, `drop` with a `confirm()` dialog; and (b) document-level `stopDefault` handlers for `dragenter`, `dragover`, and `drop` to prevent browser navigation on missed drops
- `doUpload()` which POSTs pending files and calls `editor.replaceRange(data, editor.getCursor())` to insert the returned markdown

The backend endpoint handles any file type and returns markdown (`[image:id]` or `[file:id]`) to insert at cursor. No backend changes are needed.

**CSRF note:** `CSRFProtect` is not initialized in the app factory, so CSRF validation only occurs when `form.validate_on_submit()` is called. `wiki_do_upload_from_edit` reads `request.files` directly without form validation, so no CSRF token is required in the upload request. The WTForms `hidden_tag()` present in the template's hidden upload form is unused by the AJAX path and can be ignored.

## Approach

Extend `upload.js` in place (Option A). Add paste support and replace the partial drag-drop implementation with a full-page handler.

## Design

### 1. Clipboard Paste

- Register with jQuery inside `$(document).ready()`: `$(document).on('paste', handler)` (consistent with the rest of `upload.js`)
- Listen for `paste` on `document`
- Scan `event.clipboardData.items` for items where `item.kind === 'file'`
- For each such item, call `item.getAsFile()` to get a Blob
- Name the file using a timestamped name with extension derived from `item.type` (the MIME type):
  - Images (`item.type` starts with `image/`): `pasted-image-<timestamp>.<ext>` (e.g. `pasted-image-20260317-143022.png`)
  - Other types: `pasted-file-<timestamp>.<ext>` (e.g. `pasted-file-20260317-143022.pdf`); if the MIME type is unknown or yields no extension, omit the extension
  - Timestamp format: `YYYYMMDD-HHmmss` in local time using JS `Date` methods (e.g. `new Date()` → zero-padded year/month/day/hours/minutes/seconds)
- Collect all resulting `File` objects into a plain JS array
- **Only if** the array is non-empty: call `addFiles(array)` + `doUpload()`, then call `event.preventDefault()`
- If no file items are present, do nothing — text paste falls through to CodeMirror normally (do NOT call `preventDefault()`)

### 2. Drag-and-Drop

- Remove the entire existing `initDropbox()` function and its `#out`-scoped and document-level handlers
- Register all handlers using jQuery: `$(document).on('dragenter', ...)`, `$(document).on('dragover', ...)`, etc. (consistent with the rest of `upload.js`; `e` will be a jQuery event object)
- Replace with a single set of document-level handlers:
  - `dragenter`: increment depth counter; if counter becomes 1, show the overlay; call `e.preventDefault()` and `e.stopPropagation()`
  - `dragover`: call `e.preventDefault()` and `e.stopPropagation()` (required to allow drop)
  - `dragleave`: check first — if `e.originalEvent.relatedTarget === null` or `!document.documentElement.contains(e.originalEvent.relatedTarget)`, force-reset counter to 0, hide overlay, and return; otherwise decrement using `counter = Math.max(0, counter - 1)` and hide overlay if counter reaches 0; call `e.preventDefault()` and `e.stopPropagation()`
  - `drop`: reset counter to 0; hide overlay; call `e.preventDefault()` and `e.stopPropagation()`; get `files = e.originalEvent.dataTransfer.files` (jQuery event object; `dataTransfer` must be accessed via `e.originalEvent`); **only if** `files.length > 0`, call `addFiles(files)` + `doUpload()`
- The `drop` handler on `document` serves as the sole replacement for the old `stopDefault` drop registration — combining both concerns (prevent navigation + process files)
- Remove the existing `confirm()` dialog

### 3. Visual Feedback

- Add a fixed-position full-page overlay div (hidden by default) with centered "Drop files here" text
- The overlay is shown on `dragenter` and hidden on `dragleave`/`drop`
- Semi-transparent dark background with white text for visibility over both the editor and preview panels

### 4. Edge Cases

- Paste with no file items → do nothing (text paste unaffected)
- Drop with zero files → do nothing
- Browser/OS may not always expose non-image clipboard files (behavior is browser-dependent); the handler works whenever the file is available and silently does nothing otherwise
- **Rapid paste/drop race condition (pre-existing):** `PENDING_FILES` is a global array shared between `addFiles()` and `doUpload()`. If a second upload is triggered before the first XHR completes, files from both batches accumulate in `PENDING_FILES` and the `splice` on success clears all of them. This is a pre-existing limitation of the current architecture (it also affects the file picker path) and is out of scope for this feature.

## Scope Notes

- `app/static/js/upload.js` is a separate file for the standalone upload popup page (`wiki_upload_file.html`); it is not loaded on the editor page and is not modified by this feature.

## Files Changed

| File | Change |
|------|--------|
| `app/static/editor/upload.js` | Add paste handler; replace `#out` drag-drop with document-level handler + overlay show/hide; remove `confirm()` |
| `app/static/editor/editor.css` | Add drag-over overlay styles (fixed, full-page, semi-transparent) |

No backend changes required.
