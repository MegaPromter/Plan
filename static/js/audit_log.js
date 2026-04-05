/**
 * audit_log.js — SPA журнала аудита.
 *
 * Вся конфигурация таблицы (столбцы, фильтры, сортировка) описана
 * в единственном массиве COLUMNS. Добавление/удаление столбца —
 * одна правка в этом массиве.
 */
;(function () {
  'use strict'

  // ══════════════════════════════════════════════════════════════════════
  //  КОНФИГУРАЦИЯ СТОЛБЦОВ
  //  key        — ключ поля в JSON ответа API
  //  label      — заголовок колонки
  //  sortable   — разрешена ли сортировка по колонке
  //  sortKey    — ключ для параметра sort (если отличается от key)
  //  filterable — показывать инпут-фильтр в шапке
  //  filterKey  — ключ GET-параметра фильтра (если отличается от key)
  //  filterType — 'text' | 'select' | 'date-range'
  //  options    — массив {value, label} для select-фильтра
  //  width      — CSS width для th
  //  render     — функция кастомного рендера ячейки (item, value) => html
  //  thStyle    — дополнительный inline-стиль для th
  //  tdStyle    — дополнительный inline-стиль для td
  // ══════════════════════════════════════════════════════════════════════

  var COLUMNS = [
    {
      key: '_index',
      label: '№',
      width: '50px',
      sortable: false,
      filterable: false,
      tdStyle: 'text-align:center;color:var(--muted);font-size:12px;',
      render: function (_item, _val, idx) { return idx + 1 }
    },
    {
      key: 'date',
      label: 'Дата',
      width: '100px',
      sortable: true,
      filterable: true,
      filterType: 'date-range',
      filterKey: 'date',
      tdStyle: 'white-space:nowrap;font-size:13px;',
    },
    {
      key: 'created_at',
      label: 'Время',
      width: '80px',
      sortable: true,
      filterable: false,
      tdStyle: 'white-space:nowrap;font-size:13px;color:var(--muted);',
      render: function (_item, val) {
        // из "03.04.2026 14:35" берём только время
        return val ? val.split(' ')[1] || val : ''
      }
    },
    {
      key: 'user',
      label: 'Пользователь',
      sortable: true,
      filterable: true,
      filterType: 'text',
      filterKey: 'user',
    },
    {
      key: 'action_display',
      label: 'Действие',
      sortable: true,
      sortKey: 'action',
      filterable: true,
      filterType: 'select',
      filterKey: 'action',
      options: [
        { value: '', label: 'Все' },
        { value: 'task_create', label: 'Создание задачи' },
        { value: 'task_update', label: 'Изменение задачи' },
        { value: 'task_delete', label: 'Удаление задачи' },
        { value: 'pp_create', label: 'Создание ПП' },
        { value: 'pp_update', label: 'Изменение ПП' },
        { value: 'pp_delete', label: 'Удаление ПП' },
        { value: 'pp_sync', label: 'Синхронизация ПП' },
        { value: 'dep_create', label: 'Создание зависимости' },
        { value: 'dep_update', label: 'Изменение зависимости' },
        { value: 'dep_delete', label: 'Удаление зависимости' },
        { value: 'dep_align', label: 'Выравнивание дат' },
        { value: 'role_change', label: 'Смена роли' },
        { value: 'user_create', label: 'Создание пользователя' },
        { value: 'user_delete', label: 'Удаление пользователя' },
        { value: 'cs_create', label: 'Создание набора изменений' },
        { value: 'cs_submit', label: 'Отправка на согласование' },
        { value: 'cs_approve', label: 'Утверждение' },
        { value: 'cs_reject', label: 'Отклонение' },
        { value: 'comment_delete', label: 'Удаление комментария' },
      ],
      render: function (_item, val) {
        return '<span class="badge badge-info" style="font-size:11px;">' + escHtml(val) + '</span>'
      }
    },
    {
      key: 'object_repr',
      label: 'Объект',
      sortable: true,
      filterable: true,
      filterType: 'text',
      filterKey: 'search',
      tdStyle: 'max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;',
    },
    {
      key: 'details',
      label: 'Детали',
      sortable: false,
      filterable: false,
      render: function (_item, val) {
        if (!val || !Object.keys(val).length) return '—'
        var json = JSON.stringify(val)
        return '<span class="audit-details-cell" title="' + escHtml(json) + '">' +
          escHtml(json.substring(0, 60)) + '</span>'
      }
    },
    {
      key: 'ip_address',
      label: 'IP',
      width: '120px',
      sortable: true,
      filterable: true,
      filterType: 'text',
      filterKey: 'ip',
      tdStyle: 'font-size:12px;color:var(--muted);',
      render: function (_item, val) { return escHtml(val || '—') }
    },
  ]

  // ══════════════════════════════════════════════════════════════════════
  //  СОСТОЯНИЕ
  // ══════════════════════════════════════════════════════════════════════
  var state = {
    page: 1,
    perPage: 50,
    sort: 'created_at',
    dir: 'desc',
    filters: {},         // filterKey → value
    dateFrom: '',        // для date-range
    dateTo: '',
  }

  // ══════════════════════════════════════════════════════════════════════
  //  УТИЛИТЫ
  // ══════════════════════════════════════════════════════════════════════
  function escHtml(s) {
    if (!s) return ''
    var d = document.createElement('div')
    d.textContent = s
    return d.innerHTML
  }

  function apiHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || document.cookie.split('csrftoken=')[1]?.split(';')[0] || ''
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  //  РЕНДЕР ШАПКИ (заголовки + фильтры) — из COLUMNS
  // ══════════════════════════════════════════════════════════════════════
  function renderThead() {
    var thead = document.querySelector('#auditTable thead')
    if (!thead) return

    // --- Строка заголовков ---
    var headerHtml = '<tr>'
    COLUMNS.forEach(function (col) {
      var style = ''
      if (col.width) style += 'width:' + col.width + ';'
      if (col.thStyle) style += col.thStyle

      var sortIcon = ''
      if (col.sortable) {
        var sk = col.sortKey || col.key
        if (state.sort === sk) {
          sortIcon = state.dir === 'asc'
            ? ' <i class="fas fa-sort-up" style="opacity:0.7;"></i>'
            : ' <i class="fas fa-sort-down" style="opacity:0.7;"></i>'
        } else {
          sortIcon = ' <i class="fas fa-sort" style="opacity:0.2;"></i>'
        }
      }

      var cls = col.sortable ? 'class="sortable" data-sort-key="' + (col.sortKey || col.key) + '"' : ''
      headerHtml += '<th style="' + style + '" ' + cls + '>' + escHtml(col.label) + sortIcon + '</th>'
    })
    headerHtml += '</tr>'

    // --- Строка фильтров ---
    var filterHtml = '<tr class="filter-row">'
    COLUMNS.forEach(function (col) {
      if (!col.filterable) {
        filterHtml += '<th></th>'
        return
      }

      var fk = col.filterKey || col.key

      if (col.filterType === 'select') {
        var selHtml = '<select data-filter="' + fk + '" style="width:100%;padding:4px 6px;font-size:12px;' +
          'border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text);font-family:var(--font);">'
        ;(col.options || []).forEach(function (opt) {
          var sel = state.filters[fk] === opt.value ? ' selected' : ''
          selHtml += '<option value="' + opt.value + '"' + sel + '>' + escHtml(opt.label) + '</option>'
        })
        selHtml += '</select>'
        filterHtml += '<th>' + selHtml + '</th>'
      } else if (col.filterType === 'date-range') {
        filterHtml += '<th style="padding:2px 4px;">' +
          '<input type="date" data-filter="date_from" value="' + (state.dateFrom || '') + '" ' +
          'style="width:100%;padding:3px 4px;font-size:11px;border:1px solid var(--border);border-radius:4px;' +
          'background:var(--surface);color:var(--text);font-family:var(--font);margin-bottom:2px;" title="С даты">' +
          '<input type="date" data-filter="date_to" value="' + (state.dateTo || '') + '" ' +
          'style="width:100%;padding:3px 4px;font-size:11px;border:1px solid var(--border);border-radius:4px;' +
          'background:var(--surface);color:var(--text);font-family:var(--font);" title="По дату">' +
          '</th>'
      } else {
        // text
        var val = state.filters[fk] || ''
        filterHtml += '<th>' +
          '<input type="text" data-filter="' + fk + '" value="' + escHtml(val) + '" ' +
          'placeholder="Фильтр..." ' +
          'style="width:100%;padding:4px 6px;font-size:12px;border:1px solid var(--border);' +
          'border-radius:4px;background:var(--surface);color:var(--text);font-family:var(--font);">' +
          '</th>'
      }
    })
    filterHtml += '</tr>'

    thead.innerHTML = headerHtml + filterHtml

    // --- Обработчики: сортировка ---
    thead.querySelectorAll('th.sortable').forEach(function (th) {
      th.style.cursor = 'pointer'
      th.addEventListener('click', function () {
        var sk = th.getAttribute('data-sort-key')
        if (state.sort === sk) {
          state.dir = state.dir === 'asc' ? 'desc' : 'asc'
        } else {
          state.sort = sk
          state.dir = 'asc'
        }
        state.page = 1
        loadAuditLog()
      })
    })

    // --- Обработчики: фильтры ---
    var debounceTimer = null
    thead.querySelectorAll('[data-filter]').forEach(function (el) {
      var fk = el.getAttribute('data-filter')

      if (el.tagName === 'SELECT') {
        el.addEventListener('change', function () {
          state.filters[fk] = el.value
          state.page = 1
          loadAuditLog()
        })
      } else if (fk === 'date_from' || fk === 'date_to') {
        el.addEventListener('change', function () {
          if (fk === 'date_from') state.dateFrom = el.value
          else state.dateTo = el.value
          state.page = 1
          loadAuditLog()
        })
      } else {
        // text — debounce 300ms
        el.addEventListener('input', function () {
          clearTimeout(debounceTimer)
          debounceTimer = setTimeout(function () {
            state.filters[fk] = el.value.trim()
            state.page = 1
            loadAuditLog()
          }, 300)
        })
        el.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') {
            clearTimeout(debounceTimer)
            state.filters[fk] = el.value.trim()
            state.page = 1
            loadAuditLog()
          }
        })
      }
    })
  }

  /** Обновить иконки сортировки без перерисовки фильтров */
  function updateSortIcons() {
    document.querySelectorAll('#auditTable thead th.sortable').forEach(function (th) {
      var sk = th.getAttribute('data-sort-key')
      var icon = th.querySelector('i')
      if (!icon) return
      if (state.sort === sk) {
        icon.className = state.dir === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down'
        icon.style.opacity = '0.7'
      } else {
        icon.className = 'fas fa-sort'
        icon.style.opacity = '0.2'
      }
    })
  }

  // ══════════════════════════════════════════════════════════════════════
  //  ЗАГРУЗКА ДАННЫХ
  // ══════════════════════════════════════════════════════════════════════
  async function loadAuditLog() {
    updateSortIcons()
    var params = new URLSearchParams({
      page: state.page,
      per_page: state.perPage,
      sort: state.sort,
      dir: state.dir,
    })

    // Применяем фильтры
    Object.keys(state.filters).forEach(function (k) {
      if (state.filters[k]) params.set(k, state.filters[k])
    })
    if (state.dateFrom) params.set('date_from', state.dateFrom)
    if (state.dateTo) params.set('date_to', state.dateTo)

    var colCount = COLUMNS.length
    var tbody = document.getElementById('auditBody')
    tbody.innerHTML = skeletonRows(5, colCount)

    try {
      var res = await fetch('/api/audit_log/?' + params.toString(), { headers: apiHeaders() })
      if (!res.ok) {
        tbody.innerHTML = '<tr><td colspan="' + colCount + '" style="padding:20px;text-align:center;color:var(--danger);">Ошибка загрузки</td></tr>'
        return
      }
      var data = await res.json()
      renderAuditTable(data)
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" style="padding:20px;text-align:center;color:var(--danger);">Ошибка сети</td></tr>'
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  //  РЕНДЕР ТАБЛИЦЫ (тело + пагинация) — из COLUMNS
  // ══════════════════════════════════════════════════════════════════════
  function renderAuditTable(data) {
    var tbody = document.getElementById('auditBody')
    var colCount = COLUMNS.length

    if (!data.items.length) {
      tbody.innerHTML = '<tr><td colspan="' + colCount + '" style="padding:40px;text-align:center;color:var(--muted);">' +
        '<i class="fas fa-inbox" style="font-size:24px;opacity:0.3;display:block;margin-bottom:8px;"></i>Нет записей</td></tr>'
      document.getElementById('auditPager').innerHTML = ''
      return
    }

    var offset = (data.page - 1) * data.per_page
    tbody.innerHTML = data.items.map(function (item, i) {
      var html = '<tr>'
      COLUMNS.forEach(function (col) {
        var val = col.key === '_index' ? null : item[col.key]
        var cell
        if (col.render) {
          cell = col.render(item, val, offset + i)
        } else {
          cell = escHtml(val != null ? String(val) : '—')
        }
        var style = col.tdStyle || ''
        html += '<td style="' + style + '">' + cell + '</td>'
      })
      html += '</tr>'
      return html
    }).join('')

    // Пагинация
    var totalPages = Math.ceil(data.total / data.per_page)
    var pager = document.getElementById('auditPager')
    if (totalPages <= 1) { pager.innerHTML = ''; return }

    var html = '<button ' + (state.page <= 1 ? 'disabled' : '') + ' id="auditPrev">\u2190 Назад</button>'
    html += '<span style="color:var(--muted);font-size:13px;">Стр. ' + data.page + ' из ' + totalPages + ' (' + data.total + ' записей)</span>'
    html += '<button ' + (state.page >= totalPages ? 'disabled' : '') + ' id="auditNext">Вперёд \u2192</button>'
    pager.innerHTML = html

    document.getElementById('auditPrev')?.addEventListener('click', function () {
      state.page--
      loadAuditLog()
    })
    document.getElementById('auditNext')?.addEventListener('click', function () {
      state.page++
      loadAuditLog()
    })
  }

  // ══════════════════════════════════════════════════════════════════════
  //  ИНИЦИАЛИЗАЦИЯ
  // ══════════════════════════════════════════════════════════════════════
  renderThead()
  loadAuditLog()

})()
