/**
 * drag-sort.js — Generic drag & drop row reordering for tables.
 *
 * Usage:
 *   initDragSort(tableSelector, { onReorder, handleSelector, apiUrl })
 *
 * Rows opt-in via data-draggable="true" on <tr>.
 * A drag handle (⋮⋮) is prepended to the first <td> of each draggable row.
 *
 * Options:
 *   tableSelector  — CSS selector for the <table> element
 *   onReorder(order) — callback after drop; receives [{id, index, el}, ...]
 *   handleSelector   — custom selector for the drag handle (default: '.drag-handle')
 *   apiUrl           — if provided, POST new order as JSON [{id, position}, ...]
 */
(function () {
  'use strict';

  window.initDragSort = function (tableSelector, opts) {
    opts = opts || {};
    var table = document.querySelector(tableSelector);
    if (!table) return;

    var tbody = table.querySelector('tbody');
    if (!tbody) return;

    var handleSel = opts.handleSelector || '.drag-handle';
    var dragEl = null;
    var placeholder = null;
    var startY = 0;
    var rowHeight = 0;

    // ── Inject drag handles into draggable rows ──────────────────────
    function injectHandles() {
      var rows = tbody.querySelectorAll('tr[data-draggable="true"]');
      rows.forEach(function (row) {
        if (row.querySelector(handleSel)) return; // already has handle
        var firstTd = row.querySelector('td');
        if (!firstTd) return;
        var handle = document.createElement('span');
        handle.className = 'drag-handle';
        handle.setAttribute('title', 'Перетащить');
        handle.textContent = '\u22EE\u22EE'; // ⋮⋮
        handle.setAttribute('draggable', 'true');
        firstTd.insertBefore(handle, firstTd.firstChild);
      });
    }

    // ── Create placeholder row ───────────────────────────────────────
    function createPlaceholder(cols) {
      var tr = document.createElement('tr');
      tr.className = 'drag-placeholder-row';
      var td = document.createElement('td');
      td.colSpan = cols;
      var line = document.createElement('div');
      line.className = 'drag-placeholder';
      td.appendChild(line);
      tr.appendChild(td);
      return tr;
    }

    // ── Count visible columns ────────────────────────────────────────
    function colCount() {
      var firstRow = tbody.querySelector('tr');
      if (!firstRow) return 1;
      var count = 0;
      var cells = firstRow.querySelectorAll('td');
      cells.forEach(function (td) {
        count += parseInt(td.getAttribute('colspan') || '1', 10);
      });
      return count || 1;
    }

    // ── Clear all drag-over classes ──────────────────────────────────
    function clearOverClasses() {
      tbody.querySelectorAll('.drag-over-top, .drag-over-bottom').forEach(function (el) {
        el.classList.remove('drag-over-top', 'drag-over-bottom');
      });
    }

    // ── Collect new order and fire callbacks ─────────────────────────
    function emitOrder() {
      var rows = tbody.querySelectorAll('tr[data-draggable="true"]');
      var order = [];
      rows.forEach(function (row, i) {
        order.push({
          id: row.dataset.id || row.dataset.pk || '',
          index: i,
          el: row,
        });
      });
      if (opts.onReorder) opts.onReorder(order);
      if (opts.apiUrl) saveOrder(order);
    }

    // ── Save order to server ─────────────────────────────────────────
    function saveOrder(order) {
      var payload = order.map(function (item) {
        return { id: item.id, position: item.index };
      });
      var csrfEl =
        document.querySelector('[name=csrfmiddlewaretoken]') ||
        document.querySelector('meta[name="csrf-token"]');
      var csrfToken = csrfEl ? csrfEl.value || csrfEl.content || '' : '';

      fetch(opts.apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken,
        },
        body: JSON.stringify(payload),
      }).catch(function (err) {
        console.warn('[drag-sort] Failed to save order:', err);
      });
    }

    // ── Event: dragstart ─────────────────────────────────────────────
    tbody.addEventListener('dragstart', function (e) {
      var handle = e.target.closest(handleSel);
      if (!handle) {
        e.preventDefault();
        return;
      }
      var row = handle.closest('tr[data-draggable="true"]');
      if (!row) {
        e.preventDefault();
        return;
      }

      dragEl = row;
      rowHeight = row.offsetHeight;
      startY = e.clientY;

      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', '');

      // Deferred class add so the browser captures the row for the ghost image
      requestAnimationFrame(function () {
        if (dragEl) dragEl.classList.add('dragging');
      });

      placeholder = createPlaceholder(colCount());
    });

    // ── Event: dragover ──────────────────────────────────────────────
    tbody.addEventListener('dragover', function (e) {
      if (!dragEl) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';

      var target = e.target.closest('tr[data-draggable="true"]');
      if (!target || target === dragEl) return;

      clearOverClasses();

      var rect = target.getBoundingClientRect();
      var midY = rect.top + rect.height / 2;
      var isAbove = e.clientY < midY;

      if (isAbove) {
        target.classList.add('drag-over-top');
        tbody.insertBefore(placeholder, target);
      } else {
        target.classList.add('drag-over-bottom');
        if (target.nextSibling) {
          tbody.insertBefore(placeholder, target.nextSibling);
        } else {
          tbody.appendChild(placeholder);
        }
      }
    });

    // ── Event: dragleave ─────────────────────────────────────────────
    tbody.addEventListener('dragleave', function (e) {
      var target = e.target.closest('tr[data-draggable="true"]');
      if (target) {
        target.classList.remove('drag-over-top', 'drag-over-bottom');
      }
    });

    // ── Event: drop ──────────────────────────────────────────────────
    tbody.addEventListener('drop', function (e) {
      e.preventDefault();
      if (!dragEl || !placeholder) return;

      // Insert dragged row where the placeholder is
      if (placeholder.parentNode) {
        placeholder.parentNode.insertBefore(dragEl, placeholder);
        placeholder.remove();
      }

      cleanup();
      emitOrder();
    });

    // ── Event: dragend (fallback / cancel) ───────────────────────────
    tbody.addEventListener('dragend', function () {
      cleanup();
    });

    // ── Cleanup helper ───────────────────────────────────────────────
    function cleanup() {
      if (dragEl) {
        dragEl.classList.remove('dragging');
        dragEl = null;
      }
      if (placeholder && placeholder.parentNode) {
        placeholder.remove();
      }
      placeholder = null;
      clearOverClasses();
    }

    // ── MutationObserver: auto-inject handles on new rows ────────────
    var observer = new MutationObserver(function (mutations) {
      var needsInject = false;
      mutations.forEach(function (m) {
        if (m.addedNodes.length) needsInject = true;
      });
      if (needsInject) injectHandles();
    });
    observer.observe(tbody, { childList: true });

    // Initial injection
    injectHandles();

    // Return API for external control
    return {
      refresh: injectHandles,
      destroy: function () {
        observer.disconnect();
        tbody.querySelectorAll(handleSel).forEach(function (h) {
          h.remove();
        });
      },
    };
  };
})();
