/* structure.js — SortableJS drag-and-drop tree editor + inline rename */
(function ($) {
    'use strict';

    var scriptEl   = document.getElementById('structure-script');
    var saveUrl    = scriptEl ? scriptEl.getAttribute('data-save-url') : '';
    var renameBase = scriptEl ? scriptEl.getAttribute('data-rename-base') : '';
    var csrfToken  = scriptEl ? scriptEl.getAttribute('data-csrf') : '';

    var alertEl = document.getElementById('structure-alert');

    function showAlert(msg, type) {
        alertEl.className = 'alert alert-' + (type || 'success');
        alertEl.textContent = msg;
        alertEl.style.display = 'block';
        setTimeout(function () { alertEl.style.display = 'none'; }, 4000);
    }

    /* ── Sortable initialisation (recursive) ── */
    var sortableOptions = {
        group: 'structure',
        handle: '.struct-handle',
        animation: 150,
        ghostClass: 'sortable-ghost',
        fallbackOnBody: true,
        swapThreshold: 0.65,
    };

    function initSortable(el) {
        if (!el) return;
        Sortable.create(el, sortableOptions);
        /* Recurse into nested lists */
        var nested = el.querySelectorAll('.structure-list');
        nested.forEach(function (ul) { Sortable.create(ul, sortableOptions); });
    }

    initSortable(document.getElementById('structure-tree'));
    initSortable(document.getElementById('structure-orphans'));

    /* ── Tree serialization ── */
    function serializeList(ul) {
        if (!ul) return [];
        var result = [];
        var items = ul.querySelectorAll(':scope > li');
        items.forEach(function (li) {
            var id = li.getAttribute('data-id');
            if (!id) return;
            var childUl = li.querySelector(':scope > .structure-list');
            result.push({ id: id, children: serializeList(childUl) });
        });
        return result;
    }

    function serializeOrphans(ul) {
        if (!ul) return [];
        var result = [];
        var items = ul.querySelectorAll(':scope > li');
        items.forEach(function (li) {
            var id = li.getAttribute('data-id');
            if (id) result.push(id);
        });
        return result;
    }

    /* ── Save ── */
    document.getElementById('structure-save-btn').addEventListener('click', function () {
        var tree    = serializeList(document.getElementById('structure-tree'));
        var orphans = serializeOrphans(document.getElementById('structure-orphans'));

        $.ajax({
            url: saveUrl,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ tree: tree, orphans: orphans }),
            success: function (data) {
                if (data.ok) {
                    showAlert('Saved successfully.', 'success');
                } else {
                    showAlert('Error: ' + (data.error || 'Unknown error'), 'danger');
                }
            },
            error: function (xhr) {
                var msg = 'Save failed.';
                try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e) {}
                showAlert(msg, 'danger');
            }
        });
    });

    /* ── Inline rename ── */
    $(document).on('click', '.struct-rename-btn', function () {
        var row      = $(this).closest('.struct-row');
        var titleEl  = row.find('.struct-title');
        var li       = $(this).closest('li');
        var pageId   = li.attr('data-id');
        var oldTitle = titleEl.text().trim();

        /* Build rename URL: /<group>/<page_id>/rename */
        var renameUrl = renameBase + pageId + '/rename';

        /* Replace span with input */
        var input = $('<input class="struct-rename-input" type="text">')
            .val(oldTitle);
        titleEl.replaceWith(input);
        input.focus().select();
        $(this).hide();

        function commitRename() {
            var newTitle = input.val().trim();
            if (!newTitle || newTitle === oldTitle) {
                input.replaceWith($('<span class="struct-title">').text(oldTitle));
                row.find('.struct-rename-btn').show();
                return;
            }
            $.ajax({
                url: renameUrl,
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                data: { new_title: newTitle, csrf_token: csrfToken },
                success: function (data) {
                    if (data.ok) {
                        input.replaceWith($('<span class="struct-title">').text(data.new_title));
                    } else {
                        showAlert('Rename failed: ' + (data.error || ''), 'danger');
                        input.replaceWith($('<span class="struct-title">').text(oldTitle));
                    }
                    row.find('.struct-rename-btn').show();
                },
                error: function () {
                    showAlert('Rename request failed.', 'danger');
                    input.replaceWith($('<span class="struct-title">').text(oldTitle));
                    row.find('.struct-rename-btn').show();
                }
            });
        }

        input.on('blur', commitRename);
        input.on('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); input.off('blur'); commitRename(); }
            if (e.key === 'Escape') {
                input.off('blur');
                input.replaceWith($('<span class="struct-title">').text(oldTitle));
                row.find('.struct-rename-btn').show();
            }
        });
    });

}(jQuery));
