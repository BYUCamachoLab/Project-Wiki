# Paste and Drag-and-Drop Upload Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add clipboard paste and full-page drag-and-drop upload to the wiki page editor, inserting the resulting markdown at the cursor position.

**Architecture:** Extend `app/static/editor/upload.js` to replace the existing partial drag-drop implementation with document-level jQuery handlers using a depth counter and a visual overlay. Add a paste handler that extracts file items from `clipboardData`. CSS-only change to `editor.css` adds the overlay styles.

**Tech Stack:** jQuery 3.2.1 (already loaded), plain HTML/CSS, existing Flask upload endpoint at `POST /do-upload/from-edit/<group>`.

**Spec:** `docs/superpowers/specs/2026-03-17-paste-and-drag-drop-upload-design.md`

---

## File Map

| File | Change |
|------|--------|
| `app/static/editor/editor.css` | Add `#drag-overlay` styles |
| `app/static/editor/upload.js` | Full rewrite: remove `initDropbox()`, add document-level drag handlers with depth counter + overlay toggle, add clipboard paste handler, add `getTimestamp()` and `mimeToExt()` helpers |

`app/static/js/upload.js` — **do not touch.** This is the separate popup upload page, not the editor.

---

## Task 1: Add drag overlay CSS

**Files:**
- Modify: `app/static/editor/editor.css`

- [ ] **Step 1: Add overlay styles to the end of `editor.css`**

Append the following to `app/static/editor/editor.css`:

```css
#drag-overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.65);
    color: white;
    font-size: 2em;
    font-weight: bold;
    z-index: 9999;
    pointer-events: none;
    align-items: center;
    justify-content: center;
}

#drag-overlay.active {
    display: flex;
}
```

**Why `display: none` + `.active { display: flex }`:** jQuery `.show()` sets `display: block`, which breaks flexbox centering. Using a CSS class to toggle between `none` and `flex` avoids this.

- [ ] **Step 2: Commit**

```bash
git add app/static/editor/editor.css
git commit -m "feat: add drag-over overlay styles to editor"
```

---

## Task 2: Rewrite `upload.js`

**Files:**
- Modify: `app/static/editor/upload.js`

The existing file is 94 lines. Replace it entirely with the implementation below.

**Key changes from existing code:**
- `initDropbox()` is removed entirely (both its `#out`-scoped handlers and its document-level `stopDefault` registrations)
- A `dragCounter` module-level variable is added alongside `PENDING_FILES`
- Two helper functions are added: `getTimestamp()` and `mimeToExt()`
- `$(document).ready()` now: creates the overlay div, registers paste handler, registers four drag handlers
- `addFiles()` and `doUpload()` are **unchanged**

- [ ] **Step 1: Replace `upload.js` with the full implementation**

Replace the entire content of `app/static/editor/upload.js` with:

```javascript
// List of pending files to handle when the Upload button is finally clicked.
var PENDING_FILES = [];
var dragCounter = 0;

$(document).ready(function() {
    // Create the drag-over overlay
    $('body').append('<div id="drag-overlay">Drop files here</div>');

    // Set up the handler for the file input box.
    $("#file-picker").on("change", function() {
        addFiles(this.files);
        doUpload();
    });

    // Clipboard paste handler
    $(document).on('paste', function(e) {
        var items = e.originalEvent.clipboardData && e.originalEvent.clipboardData.items;
        if (!items) { return; }
        var files = [];
        var timestamp = getTimestamp();
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            if (item.kind !== 'file') { continue; }
            var blob = item.getAsFile();
            if (!blob) { continue; }
            var isImage = item.type.indexOf('image/') === 0;
            var prefix = isImage ? 'pasted-image-' : 'pasted-file-';
            var ext = mimeToExt(item.type);
            var name = prefix + timestamp + (ext ? '.' + ext : '');
            files.push(new File([blob], name, { type: item.type }));
        }
        if (files.length > 0) {
            addFiles(files);
            doUpload();
            e.preventDefault();
        }
    });

    // Full-page drag-and-drop handlers
    $(document).on('dragenter', function(e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter++;
        if (dragCounter === 1) {
            $('#drag-overlay').addClass('active');
        }
    });

    $(document).on('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
    });

    $(document).on('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var rt = e.originalEvent.relatedTarget;
        if (rt === null || !document.documentElement.contains(rt)) {
            // Cursor left the browser window — force reset
            dragCounter = 0;
            $('#drag-overlay').removeClass('active');
            return;
        }
        dragCounter = Math.max(0, dragCounter - 1);
        if (dragCounter === 0) {
            $('#drag-overlay').removeClass('active');
        }
    });

    $(document).on('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        dragCounter = 0;
        $('#drag-overlay').removeClass('active');
        var files = e.originalEvent.dataTransfer.files;
        if (files.length > 0) {
            addFiles(files);
            doUpload();
        }
    });
});

function getTimestamp() {
    var d = new Date();
    var pad = function(n) { return String(n).padStart(2, '0'); };
    return '' + d.getFullYear() +
        pad(d.getMonth() + 1) +
        pad(d.getDate()) + '-' +
        pad(d.getHours()) +
        pad(d.getMinutes()) +
        pad(d.getSeconds());
}

function mimeToExt(mimeType) {
    var map = {
        'image/png':  'png',
        'image/jpeg': 'jpg',
        'image/gif':  'gif',
        'image/webp': 'webp',
        'image/svg+xml': 'svg',
        'application/pdf': 'pdf',
        'application/msword': 'doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.ms-excel': 'xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
        'application/vnd.ms-powerpoint': 'ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
        'text/plain': 'txt',
        'text/csv':   'csv',
        'application/zip': 'zip',
    };
    return map[mimeType] || '';
}

function addFiles(files) {
    // Add them to the pending files list.
    for (var i = 0; i < files.length; i++) {
        PENDING_FILES.push(files[i]);
    }
}

function doUpload() {
    var fd = new FormData();

    // Attach the files.
    for (var i = 0; i < PENDING_FILES.length; i++) {
        fd.append("file", PENDING_FILES[i]);
    }

    var xhr = $.ajax({
        xhr: function() {
            var xhrobj = $.ajaxSettings.xhr();
            return xhrobj;
        },
        url: '/do-upload/from-edit/' + wiki_group,
        method: "POST",
        contentType: false,
        processData: false,
        cache: false,
        data: fd,
        success: function(data) {
            //Remove the annoying new lines
            data = data.replace(/\n/g, '');
            PENDING_FILES.splice(0, PENDING_FILES.length);
            editor.replaceRange(data, editor.getCursor())
        },
    });
}
```

- [ ] **Step 2: Start the dev server and open an editor page**

```bash
python PW_run.py
```

Navigate to any wiki page and click Edit.

- [ ] **Step 3: Verify — existing Upload button still works**

Click the Upload button in the editor menu. Select any file. Confirm the file uploads and the markdown is inserted at the cursor.

- [ ] **Step 4: Verify — drag-and-drop shows overlay and uploads**

Drag any file from your file manager onto the editor page. Confirm:
- The dark "Drop files here" overlay appears while dragging
- The overlay disappears on drop
- The file uploads and markdown is inserted at the cursor

- [ ] **Step 5: Verify — dragging out of the window hides the overlay**

Start dragging a file into the editor, then move the cursor back out of the browser window without dropping. Confirm the overlay disappears.

- [ ] **Step 6: Verify — clipboard paste of an image**

Take a screenshot or copy an image to the clipboard (e.g., right-click an image in your browser → Copy Image). Click in the editor to set the cursor, then press Ctrl+V (or Cmd+V). Confirm:
- The image uploads
- A `[image:...]` markdown tag is inserted at the cursor
- Normal text paste (typing, then Ctrl+V of copied text) is unaffected

- [ ] **Step 7: Commit**

```bash
git add app/static/editor/upload.js
git commit -m "feat: add clipboard paste and full-page drag-and-drop upload to editor"
```
