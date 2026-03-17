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
