/* page-tree.js — page tree expand/collapse, sidebar collapse toggles */
(function () {
    'use strict';

    /* ── TOC Bootstrap class injection ── */
    var toc = document.getElementById('pw-toc');
    if (toc) {
        var uls = toc.getElementsByTagName('ul');
        if (uls.length > 0) {
            uls[0].className = 'nav nav-pills flex-column';
            var lis = toc.getElementsByTagName('li');
            for (var i = 0; i < lis.length; i++) {
                lis[i].className = 'nav-item';
            }
            var links = toc.getElementsByTagName('a');
            for (var j = 0; j < links.length; j++) {
                links[j].className = 'nav-link';
            }
        }
    }

    /* ── Sidebar collapse toggles ── */
    var leftSidebar  = document.getElementById('pw-sidebar-left');
    var rightSidebar = document.getElementById('pw-sidebar-right');
    var leftToggle   = document.getElementById('pw-left-toggle');
    var rightToggle  = document.getElementById('pw-right-toggle');

    function applyLeftState(collapsed) {
        if (collapsed) {
            leftSidebar.classList.add('collapsed');
            leftToggle.innerHTML = '&#xBB;';
        } else {
            leftSidebar.classList.remove('collapsed');
            leftToggle.innerHTML = '&#xAB;';
        }
    }

    function applyRightState(collapsed) {
        if (!rightSidebar || rightSidebar.classList.contains('empty')) return;
        if (collapsed) {
            rightSidebar.classList.add('collapsed');
            rightToggle.innerHTML = '&#xAB;';
        } else {
            rightSidebar.classList.remove('collapsed');
            rightToggle.innerHTML = '&#xBB;';
        }
    }

    if (leftSidebar && leftToggle) {
        var leftCollapsed = localStorage.getItem('pw_leftsidebar_collapsed') === '1';
        applyLeftState(leftCollapsed);
        leftToggle.addEventListener('click', function () {
            var isCollapsed = leftSidebar.classList.contains('collapsed');
            applyLeftState(!isCollapsed);
            localStorage.setItem('pw_leftsidebar_collapsed', isCollapsed ? '0' : '1');
        });
    }

    if (rightSidebar && rightToggle) {
        var rightCollapsed = localStorage.getItem('pw_rightsidebar_collapsed') === '1';
        applyRightState(rightCollapsed);
        rightToggle.addEventListener('click', function () {
            var isCollapsed = rightSidebar.classList.contains('collapsed');
            applyRightState(!isCollapsed);
            localStorage.setItem('pw_rightsidebar_collapsed', isCollapsed ? '0' : '1');
        });
    }

    /* ── Page tree expand/collapse ── */
    var treeEl = document.getElementById('pw-tree');
    if (!treeEl) return;

    var group      = treeEl.getAttribute('data-group') || '';
    var currentId  = treeEl.getAttribute('data-current') || '';
    var storageKey = 'pw_tree_' + group;

    /* Load persisted open-set (set of node ids that are expanded) */
    var openSet = {};
    try {
        var stored = localStorage.getItem(storageKey);
        if (stored) openSet = JSON.parse(stored);
    } catch (e) { openSet = {}; }

    function saveOpenSet() {
        try { localStorage.setItem(storageKey, JSON.stringify(openSet)); } catch (e) {}
    }

    /* Find ancestors of currentId so we can auto-expand them */
    function findAncestors(rows, targetId, path) {
        for (var i = 0; i < rows.length; i++) {
            var li = rows[i];
            var id = li.getAttribute('data-id');
            var childUl = li.querySelector(':scope > ul');
            if (id === targetId) return path.concat(id);
            if (childUl) {
                var childLis = childUl.querySelectorAll(':scope > li');
                var found = findAncestors(Array.from(childLis), targetId, path.concat(id));
                if (found) return found;
            }
        }
        return null;
    }

    /* Collect ancestor ids to auto-expand */
    var ancestorIds = {};
    if (currentId) {
        var topLis = treeEl.querySelectorAll(':scope > ul > li');
        var ancestors = findAncestors(Array.from(topLis), currentId, []);
        if (ancestors) {
            ancestors.forEach(function (id) { ancestorIds[id] = true; });
        }
    }

    /* Apply open/closed state to a <li> node */
    function applyNodeState(li, open) {
        var childUl = li.querySelector(':scope > ul');
        var toggle  = li.querySelector(':scope > .pw-tree-row > .pw-tree-toggle');
        if (!childUl) return;
        childUl.style.display = open ? '' : 'none';
        if (toggle) toggle.innerHTML = open ? '&#9660;' : '&#9654;';
    }

    /* Initialise all nodes */
    function initNodes(lis) {
        lis.forEach(function (li) {
            var id = li.getAttribute('data-id');
            var childUl = li.querySelector(':scope > ul');
            var toggle  = li.querySelector(':scope > .pw-tree-row > .pw-tree-toggle');

            var shouldOpen = !!(openSet[id] || ancestorIds[id]);
            applyNodeState(li, shouldOpen);

            if (toggle) {
                toggle.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    var isOpen = childUl && childUl.style.display !== 'none';
                    applyNodeState(li, !isOpen);
                    if (isOpen) { delete openSet[id]; } else { openSet[id] = true; }
                    saveOpenSet();
                });
            }

            /* Recurse into children */
            if (childUl) {
                var childLis = childUl.querySelectorAll(':scope > li');
                initNodes(Array.from(childLis));
            }
        });
    }

    var rootLis = treeEl.querySelectorAll(':scope > ul > li');
    initNodes(Array.from(rootLis));

    /* ── Orphans toggle ── */
    var orphansToggle = document.getElementById('pw-orphans-toggle');
    var orphansList   = document.getElementById('pw-orphans-list');
    if (orphansToggle && orphansList) {
        var orphansOpen = localStorage.getItem('pw_orphans_' + group) === '1';
        orphansList.style.display = orphansOpen ? '' : 'none';
        orphansToggle.innerHTML   = (orphansOpen ? '&#9660;' : '&#9654;') + ' Orphans';

        orphansToggle.addEventListener('click', function () {
            orphansOpen = orphansList.style.display === 'none';
            orphansList.style.display = orphansOpen ? '' : 'none';
            orphansToggle.innerHTML   = (orphansOpen ? '&#9660;' : '&#9654;') + ' Orphans';
            localStorage.setItem('pw_orphans_' + group, orphansOpen ? '1' : '0');
        });
    }

}());
