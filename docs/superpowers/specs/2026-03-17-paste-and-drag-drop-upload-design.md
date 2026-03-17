# Paste and Drag-and-Drop Upload — Design Spec

**Date:** 2026-03-17
**Status:** Approved
**Scope:** Editor page only (`wiki_page_edit.html`)

## Overview

Add clipboard paste and drag-and-drop upload support to the wiki page editor. Both methods upload files immediately and insert the resulting markdown at the current cursor position, matching the behavior of the existing Upload button.

## Background

The editor page already has:
- A hidden file input and form targeting `POST /do-upload/from-edit/<group>`
- A partial drag-drop handler on `#out` (preview panel only) with a confirmation dialog
- `doUpload()` which POSTs pending files and calls `editor.replaceRange(data, editor.getCursor())` to insert the returned markdown

The backend endpoint handles any file type and returns markdown (`[image:id]` or `[file:id]`) to insert at cursor. No backend changes are needed.

## Approach

Extend `upload.js` in place (Option A). Add paste support and replace the partial drag-drop implementation with a full-page handler.

## Design

### 1. Clipboard Paste

- Listen for `paste` on `document`
- Scan `event.clipboardData.items` for items where `item.kind === 'file'`
- For each such item, call `item.getAsFile()` to get a Blob
- Name the file:
  - Images: `pasted-image-<timestamp>.<ext>` (ext derived from MIME type, e.g. `png`, `jpeg`)
  - Other types: `pasted-file-<timestamp>` (original filename unavailable from clipboard API)
- If one or more file items are found, pass them to `addFiles()` + `doUpload()` and call `event.preventDefault()` to suppress any default paste behavior
- If no file items are present, do nothing — text paste falls through to CodeMirror normally

### 2. Drag-and-Drop

- Replace the `#out`-only drop zone with document-level drag event handlers
- Use an integer enter/leave counter to track drag depth across child elements (prevents overlay flickering)
- On `dragenter`: increment counter; if counter becomes 1, show the overlay
- On `dragleave`: decrement counter; if counter reaches 0, hide the overlay
- On `drop`: reset counter, hide overlay, call `event.preventDefault()`, pass `e.dataTransfer.files` to `addFiles()` + `doUpload()`
- Remove the existing `confirm()` dialog
- Retain the existing document-level `stopDefault` handlers for `dragenter`, `dragover`, and `drop` to prevent the browser from navigating away on accidental drops

### 3. Visual Feedback

- Add a fixed-position full-page overlay div (hidden by default) with centered "Drop files here" text
- The overlay is shown on `dragenter` and hidden on `dragleave`/`drop`
- Semi-transparent dark background with white text for visibility over both the editor and preview panels

### 4. Edge Cases

- Paste with no file items → do nothing (text paste unaffected)
- Drop with zero files → do nothing
- Browser/OS may not always expose non-image clipboard files (behavior is browser-dependent); the handler works whenever the file is available and silently does nothing otherwise

## Files Changed

| File | Change |
|------|--------|
| `app/static/editor/upload.js` | Add paste handler; replace `#out` drag-drop with document-level handler + overlay show/hide; remove `confirm()` |
| `app/static/editor/editor.css` | Add drag-over overlay styles (fixed, full-page, semi-transparent) |

No backend changes required.
