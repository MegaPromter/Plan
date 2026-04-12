/**
 * Column picker — позволяет пользователю показывать/скрывать колонки таблицы.
 * Состояние сохраняется в localStorage.
 */
function initColumnPicker(opts) {
  var tableId = opts.tableId;
  var storageKey = opts.storageKey || 'colPicker_' + tableId;
  var btnContainer = opts.btnContainer; // selector or element
  var columns = opts.columns; // [{key, label, default: true/false}]

  // Load saved state
  var saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
  } catch (e) {
    /* ignored */
  }

  var state = {};
  columns.forEach(function (col) {
    state[col.key] = Object.prototype.hasOwnProperty.call(saved, col.key)
      ? saved[col.key]
      : col.default !== false;
  });

  // Create button
  var container =
    typeof btnContainer === 'string' ? document.querySelector(btnContainer) : btnContainer;
  if (!container) return;

  var btn = document.createElement('button');
  btn.className = 'btn btn-outline btn-sm';
  btn.innerHTML = '<i class="fas fa-columns"></i> Колонки';
  btn.title = 'Показать/скрыть колонки';
  container.appendChild(btn);

  // Create dropdown
  var dropdown = document.createElement('div');
  dropdown.className = 'col-picker-dropdown';
  dropdown.style.cssText =
    'display:none;position:absolute;top:100%;right:0;z-index:100;background:var(--surface);border:1px solid var(--border);border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,0.12);padding:8px 0;min-width:220px;max-height:400px;overflow-y:auto;';

  columns.forEach(function (col) {
    var item = document.createElement('label');
    item.style.cssText =
      'display:flex;align-items:center;gap:10px;padding:8px 16px;cursor:pointer;font-size:14px;color:var(--text);transition:background 0.1s;';
    item.onmouseenter = function () {
      item.style.background = 'var(--surface2)';
    };
    item.onmouseleave = function () {
      item.style.background = '';
    };
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = state[col.key];
    cb.style.cssText = 'width:16px;height:16px;accent-color:var(--accent);';
    cb.addEventListener('change', function () {
      state[col.key] = cb.checked;
      localStorage.setItem(storageKey, JSON.stringify(state));
      applyVisibility();
    });
    item.appendChild(cb);
    item.appendChild(document.createTextNode(col.label));
    dropdown.appendChild(item);
  });

  // Reset link
  var resetWrap = document.createElement('div');
  resetWrap.style.cssText = 'border-top:1px solid var(--border);margin-top:4px;padding:8px 16px;';
  var resetLink = document.createElement('a');
  resetLink.href = '#';
  resetLink.textContent = 'Сбросить';
  resetLink.style.cssText = 'font-size:13px;color:var(--accent);text-decoration:none;';
  resetLink.onclick = function (e) {
    e.preventDefault();
    columns.forEach(function (col) {
      state[col.key] = col.default !== false;
    });
    localStorage.removeItem(storageKey);
    dropdown.querySelectorAll('input[type=checkbox]').forEach(function (cb, i) {
      cb.checked = state[columns[i].key];
    });
    applyVisibility();
  };
  resetWrap.appendChild(resetLink);
  dropdown.appendChild(resetWrap);

  var wrap = document.createElement('div');
  wrap.style.position = 'relative';
  wrap.style.display = 'inline-block';
  btn.parentNode.insertBefore(wrap, btn);
  wrap.appendChild(btn);
  wrap.appendChild(dropdown);

  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    var isOpen = dropdown.style.display !== 'none';
    dropdown.style.display = isOpen ? 'none' : 'block';
  });
  document.addEventListener('click', function (e) {
    if (!wrap.contains(e.target)) dropdown.style.display = 'none';
  });

  function applyVisibility() {
    var table = document.getElementById(tableId);
    if (!table) return;
    columns.forEach(function (col, colIdx) {
      var display = state[col.key] ? '' : 'none';
      // Use data-col attribute if present, otherwise use column index
      var selector = col.selector || '[data-col="' + col.key + '"]';
      table.querySelectorAll(selector).forEach(function (cell) {
        cell.style.display = display;
      });
      // Also try by nth-child (colIdx is 0-based, nth-child is 1-based)
      if (col.colIndex !== undefined) {
        var ci = col.colIndex + 1;
        table
          .querySelectorAll('td:nth-child(' + ci + '), th:nth-child(' + ci + ')')
          .forEach(function (cell) {
            cell.style.display = display;
          });
      }
    });
  }

  // Initial apply
  applyVisibility();

  return {
    applyVisibility: applyVisibility,
    getState: function () {
      return state;
    },
  };
}
