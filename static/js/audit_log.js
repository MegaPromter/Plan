/**
 * audit_log.js — SPA журнала аудита.
 * JS рендерит всю таблицу (thead + tbody) в #auditContent.
 * Фильтры: mf-trigger с dropdown, сортировка по клику на заголовок.
 */
(function () {
  'use strict';

  /* ── Конфигурация колонок ──────────────────────────────────── */
  var COLUMNS = [
    { key: '_index', label: '№', width: '44px', sortable: false, filterable: false },
    { key: 'date', label: 'Дата', width: '100px', sortable: true, filterable: true },
    { key: 'created_at', label: 'Время', width: '60px', sortable: true, filterable: false },
    { key: 'user', label: 'Пользователь', width: '140px', sortable: true, filterable: true },
    {
      key: 'action_display',
      label: 'Действие',
      width: '160px',
      sortable: true,
      filterable: true,
      sortKey: 'action',
    },
    { key: 'object_repr', label: 'Объект', width: '250px', sortable: true, filterable: true },
    { key: 'details', label: 'Детали', width: '200px', sortable: false, filterable: false },
    { key: 'ip_address', label: 'IP', width: '100px', sortable: true, filterable: true },
  ];

  /* ── Состояние ─────────────────────────────────────────────── */
  var state = {
    page: 1,
    perPage: 50,
    sort: 'created_at',
    dir: 'desc',
    allItems: [],
  };

  var mfActive = {};
  var mfDropdowns = {};

  /* ── Утилиты ───────────────────────────────────────────────── */
  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function apiHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken':
        document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
        document.cookie.split('csrftoken=')[1]?.split(';')[0] ||
        '',
    };
  }

  /* ── Рендер каркаса таблицы ────────────────────────────────── */
  function renderTableShell() {
    var container = document.getElementById('auditContent');
    if (!container) return;

    var headerRow = '<tr>';
    var filterRow = '<tr class="filter-row">';
    COLUMNS.forEach(function (col) {
      var w = col.width ? ' style="width:' + col.width + ';"' : '';
      var sortAttr = col.sortable ? ' data-sort="' + (col.sortKey || col.key) + '"' : '';
      headerRow += '<th' + w + sortAttr + '>' + esc(col.label) + '</th>';

      if (col.filterable) {
        filterRow +=
          '<th><div class="mf-wrap"><button class="mf-trigger" data-col="' +
          col.key +
          '">▼</button></div></th>';
      } else {
        filterRow += '<th></th>';
      }
    });
    headerRow += '</tr>';
    filterRow += '</tr>';

    container.innerHTML =
      '<div class="data-table-wrap">' +
      '<table class="data-table" id="auditTable">' +
      '<thead>' +
      headerRow +
      filterRow +
      '</thead>' +
      '<tbody id="auditBody"></tbody>' +
      '</table>' +
      '</div>';

    // Обработчики сортировки
    container.querySelectorAll('th[data-sort]').forEach(function (th) {
      th.style.cursor = 'pointer';
      th.addEventListener('click', function () {
        var sk = th.getAttribute('data-sort');
        if (state.sort === sk) {
          state.dir = state.dir === 'asc' ? 'desc' : 'asc';
        } else {
          state.sort = sk;
          state.dir = 'asc';
        }
        state.page = 1;
        loadAuditLog();
      });
    });

    // Обработчики мульти-фильтров
    container.querySelectorAll('.mf-trigger').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        toggleMf(btn);
      });
    });
  }

  /* ── Иконки сортировки ─────────────────────────────────────── */
  function updateSortIcons() {
    document.querySelectorAll('#auditTable thead th[data-sort]').forEach(function (th) {
      var sk = th.getAttribute('data-sort');
      var icon = th.querySelector('i.fa-sort, i.fa-sort-up, i.fa-sort-down');
      if (!icon) {
        icon = document.createElement('i');
        icon.style.marginLeft = '4px';
        th.appendChild(icon);
      }
      if (state.sort === sk) {
        icon.className = state.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
        icon.style.opacity = '0.7';
      } else {
        icon.className = 'fas fa-sort';
        icon.style.opacity = '0.2';
      }
    });
  }

  /* ── Мульти-фильтр: dropdown ───────────────────────────────── */
  function toggleMf(btn) {
    var col = btn.getAttribute('data-col');
    var existing = mfDropdowns[col];

    Object.values(mfDropdowns).forEach(function (dd) {
      dd.remove();
    });
    mfDropdowns = {};

    if (existing) return;

    var values = new Set();
    state.allItems.forEach(function (item) {
      var v = item[col];
      if (v !== null && v !== undefined && v !== '') values.add(String(v));
    });
    var sorted = Array.from(values).sort();

    var dd = document.createElement('div');
    dd.className = 'mf-dropdown open';
    var selected = mfActive[col] || new Set();

    var search = document.createElement('input');
    search.type = 'text';
    search.placeholder = 'Поиск...';
    search.className = 'mf-search';
    dd.appendChild(search);

    var list = document.createElement('div');
    list.className = 'mf-list';
    sorted.forEach(function (val) {
      var label = document.createElement('label');
      label.className = 'mf-option';
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.value = val;
      cb.checked = selected.has(val);
      cb.addEventListener('change', function () {
        if (!mfActive[col]) mfActive[col] = new Set();
        if (cb.checked) mfActive[col].add(val);
        else mfActive[col].delete(val);
        var cnt = mfActive[col] ? mfActive[col].size : 0;
        btn.classList.toggle('active', cnt > 0);
        btn.textContent = cnt > 0 ? cnt + ' выбр.' : '▼';
        renderFiltered();
      });
      label.appendChild(cb);
      label.appendChild(document.createTextNode(' ' + val));
      list.appendChild(label);
    });
    dd.appendChild(list);

    search.addEventListener('input', function () {
      var q = search.value.toLowerCase();
      list.querySelectorAll('label').forEach(function (l) {
        l.style.display = l.textContent.toLowerCase().includes(q) ? '' : 'none';
      });
    });

    var rect = btn.getBoundingClientRect();
    dd.style.position = 'fixed';
    dd.style.top = rect.bottom + 2 + 'px';
    dd.style.left = rect.left + 'px';
    dd.style.zIndex = '9999';

    document.body.appendChild(dd);
    mfDropdowns[col] = dd;
    search.focus();
  }

  document.addEventListener('click', function (e) {
    if (e.target.closest('.mf-dropdown') || e.target.closest('.mf-trigger')) return;
    Object.values(mfDropdowns).forEach(function (dd) {
      dd.remove();
    });
    mfDropdowns = {};
  });

  /* ── Клиентская фильтрация ─────────────────────────────────── */
  function matchesMf(item) {
    for (var col in mfActive) {
      if (mfActive[col].size === 0) continue;
      if (!mfActive[col].has(String(item[col] || ''))) return false;
    }
    return true;
  }

  function renderFiltered() {
    renderRows(state.allItems.filter(matchesMf));
  }

  /* ── Загрузка данных ───────────────────────────────────────── */
  async function loadAuditLog() {
    updateSortIcons();
    var params = new URLSearchParams({
      page: state.page,
      per_page: state.perPage,
      sort: state.sort,
      dir: state.dir,
    });

    var tbody = document.getElementById('auditBody');
    if (tbody) tbody.innerHTML = skeletonRows(5, COLUMNS.length);

    try {
      var res = await fetch('/api/audit_log/?' + params.toString(), { headers: apiHeaders() });
      if (!res.ok) {
        if (tbody)
          tbody.innerHTML =
            '<tr><td colspan="' +
            COLUMNS.length +
            '" style="padding:20px;text-align:center;color:var(--danger);">Ошибка загрузки</td></tr>';
        return;
      }
      var data = await res.json();
      state.allItems = data.items;
      renderFiltered();
      renderPager(data);
    } catch (e) {
      var tb = document.getElementById('auditBody');
      if (tb)
        tb.innerHTML =
          '<tr><td colspan="' +
          COLUMNS.length +
          '" style="padding:20px;text-align:center;color:var(--danger);">Ошибка сети</td></tr>';
    }
  }

  /* ── Рендер строк ──────────────────────────────────────────── */
  function renderRows(items) {
    var tbody = document.getElementById('auditBody');
    if (!tbody) return;

    if (!items.length) {
      tbody.innerHTML =
        '<tr><td colspan="' +
        COLUMNS.length +
        '" style="padding:40px;text-align:center;color:var(--muted);">' +
        '<i class="fas fa-inbox" style="font-size:24px;opacity:0.3;display:block;margin-bottom:8px;"></i>Нет записей</td></tr>';
      return;
    }

    var offset = (state.page - 1) * state.perPage;
    tbody.innerHTML = items
      .map(function (item, i) {
        var time = item.created_at ? item.created_at.split(' ')[1] || '' : '';
        var details = '—';
        if (item.details && Object.keys(item.details).length) {
          var json = JSON.stringify(item.details);
          details =
            '<span class="audit-details-cell" title="' +
            esc(json) +
            '">' +
            esc(json.substring(0, 50)) +
            (json.length > 50 ? '…' : '') +
            '</span>';
        }
        return (
          '<tr data-id="' +
          item.id +
          '">' +
          '<td style="text-align:center;color:var(--muted);font-size:12px;">' +
          (offset + i + 1) +
          '</td>' +
          '<td style="white-space:nowrap;font-size:13px;">' +
          esc(item.date) +
          '</td>' +
          '<td style="white-space:nowrap;font-size:13px;color:var(--muted);">' +
          esc(time) +
          '</td>' +
          '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
          esc(item.user) +
          '</td>' +
          '<td><span class="badge badge-info" style="font-size:11px;">' +
          esc(item.action_display) +
          '</span></td>' +
          '<td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
          esc(item.object_repr || '—') +
          '</td>' +
          '<td>' +
          details +
          '</td>' +
          '<td style="font-size:12px;color:var(--muted);">' +
          esc(item.ip_address || '—') +
          '</td>' +
          '</tr>'
        );
      })
      .join('');
  }

  /* ── Пагинация ─────────────────────────────────────────────── */
  function renderPager(data) {
    var totalPages = Math.ceil(data.total / data.per_page);
    var pager = document.getElementById('auditPager');
    if (!pager) return;
    if (totalPages <= 1) {
      pager.innerHTML = '';
      return;
    }

    pager.innerHTML =
      '<button ' +
      (state.page <= 1 ? 'disabled' : '') +
      ' id="auditPrev">← Назад</button>' +
      '<span style="color:var(--muted);font-size:13px;">Стр. ' +
      data.page +
      ' из ' +
      totalPages +
      ' (' +
      data.total +
      ' записей)</span>' +
      '<button ' +
      (state.page >= totalPages ? 'disabled' : '') +
      ' id="auditNext">Вперёд →</button>';

    document.getElementById('auditPrev')?.addEventListener('click', function () {
      state.page--;
      loadAuditLog();
    });
    document.getElementById('auditNext')?.addEventListener('click', function () {
      state.page++;
      loadAuditLog();
    });
  }

  /* ── Старт ─────────────────────────────────────────────────── */
  renderTableShell();
  updateSortIcons();
  loadAuditLog();
})();
