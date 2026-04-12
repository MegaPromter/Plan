/**
 * sandbox.js — Управление песочницей (Changeset) для Производственного плана.
 *
 * Глобальные функции:
 *   toggleSandboxMode()     — вкл/выкл режим песочницы
 *   exitSandbox()           — выход из песочницы
 *   openChangesetList()     — показать список наборов
 *   openCreateChangesetModal() — модал создания набора
 *   createChangeset()       — создание набора (POST)
 *   activateChangeset(id)   — активировать набор для работы
 *   submitChangeset()       — отправить на согласование
 *   approveChangeset()      — утвердить набор
 *   openRejectDialog()      — модал причины отклонения
 *   rejectChangeset()       — отклонить набор
 *   showChangesetDiff()     — показать diff
 *   addSandboxItem(action, targetRowId, fieldChanges) — добавить элемент
 */

/* global fetchJson, showToast, closeModal, esc, confirmDialog */

// ── Состояние ────────────────────────────────────────────────────────────
var sandboxMode = false;
var currentChangesetId = null;
var currentChangeset = null;
var currentPPProjectId = null; // устанавливается из production_plan.js

// ── Конфиг ───────────────────────────────────────────────────────────────
var _sbConfig = null;
function _getSbConfig() {
  if (!_sbConfig) {
    try {
      _sbConfig = JSON.parse(document.getElementById('pp-config').textContent);
    } catch (e) {
      _sbConfig = {};
    }
  }
  return _sbConfig;
}

// ══════════════════════════════════════════════════════════════════════════
//  Управление режимом песочницы
// ══════════════════════════════════════════════════════════════════════════

function toggleSandboxMode() {
  if (sandboxMode) {
    exitSandbox();
  } else {
    sandboxMode = true;
    var btn = document.getElementById('sandboxToggleBtn');
    if (btn) btn.classList.add('active');
    var label = document.getElementById('sandboxToggleLabel');
    if (label) label.textContent = 'Песочница ✓';
    openChangesetList();
  }
}

function exitSandbox() {
  sandboxMode = false;
  currentChangesetId = null;
  currentChangeset = null;

  var btn = document.getElementById('sandboxToggleBtn');
  if (btn) btn.classList.remove('active');
  var label = document.getElementById('sandboxToggleLabel');
  if (label) label.textContent = 'Песочница';

  document.getElementById('sandboxPanel').style.display = 'none';

  // Убираем визуальный режим песочницы
  var pv = document.getElementById('projectView');
  if (pv) pv.classList.remove('sandbox-active');

  // Убираем бегущую полосу
  var indicator = document.getElementById('sandboxTopbarIndicator');
  if (indicator) indicator.classList.remove('active');

  // Убираем sandbox-create строки (виртуальные)
  document.querySelectorAll('tr[data-sandbox-item]').forEach(function (el) {
    el.remove();
  });

  // Убираем sandbox-подсветку со строк
  document
    .querySelectorAll('.sandbox-create,.sandbox-update,.sandbox-delete')
    .forEach(function (el) {
      el.classList.remove('sandbox-create', 'sandbox-update', 'sandbox-delete');
    });
  document.querySelectorAll('.sandbox-cell-changed').forEach(function (el) {
    el.classList.remove('sandbox-cell-changed');
  });
  document.querySelectorAll('.sandbox-action-badge').forEach(function (el) {
    el.remove();
  });

  // Перезагружаем таблицу без overlay
  if (typeof loadPPRows === 'function') loadPPRows();
}

// ══════════════════════════════════════════════════════════════════════════
//  Список наборов
// ══════════════════════════════════════════════════════════════════════════

function openChangesetList() {
  var modal = document.getElementById('changesetListModal');
  if (!modal) return;
  modal.classList.add('open');

  var body = document.getElementById('changesetListBody');
  body.innerHTML = '<div class="skeleton-row"></div><div class="skeleton-row"></div>';

  var projectId = currentPPProjectId || _getPPProjectId();
  var url = '/api/changesets/?pp_project_id=' + projectId;

  fetchJson(url)
    .then(function (data) {
      var items = data.items || [];
      if (!items.length) {
        body.innerHTML = emptyStateHtml({
          iconHtml: '📋',
          title: 'Нет наборов изменений для этого плана',
        });
        return;
      }

      var statusColors = {
        draft: 'draft',
        review: 'review',
        approved: 'approved',
        rejected: 'rejected',
      };
      var html = '';
      items.forEach(function (cs) {
        html +=
          '<div class="cs-list-item" onclick="activateChangeset(' +
          cs.id +
          ')">' +
          '<span class="cs-title">' +
          esc(cs.title) +
          '</span>' +
          '<span class="sandbox-badge ' +
          statusColors[cs.status] +
          '">' +
          esc(cs.status_display) +
          '</span>' +
          '<span class="cs-count" title="Элементов">' +
          cs.items_count +
          '</span>' +
          '<span class="cs-meta">' +
          esc(cs.author_name) +
          '<br>' +
          _formatDate(cs.created_at) +
          '</span>' +
          '</div>';
      });
      body.innerHTML = html;
    })
    .catch(function (err) {
      body.innerHTML =
        '<div class="alert alert-error">Ошибка загрузки: ' +
        esc(err.message || String(err)) +
        '</div>';
    });
}

function _getPPProjectId() {
  // Из глобальной переменной production_plan.js
  if (window._ppCurrentProjectId) return window._ppCurrentProjectId;
  // Фолбэк: из URL-параметра ?project_id=
  var params = new URLSearchParams(location.search);
  return params.get('project_id') || '';
}

function _formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    var d = new Date(isoStr);
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch (e) {
    return isoStr;
  }
}

// ══════════════════════════════════════════════════════════════════════════
//  Создание набора
// ══════════════════════════════════════════════════════════════════════════

function openCreateChangesetModal() {
  closeModal('changesetListModal');
  document.getElementById('csTitle').value = '';
  document.getElementById('csDescription').value = '';
  document.getElementById('createChangesetModal').classList.add('open');
}

function createChangeset() {
  var title = document.getElementById('csTitle').value.trim();
  if (!title) {
    showToast('Введите название', 'warning');
    return;
  }

  var projectId = currentPPProjectId || _getPPProjectId();
  if (!projectId) {
    showToast('Не определён проект ПП', 'error');
    return;
  }

  fetchJson('/api/changesets/create/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
    body: JSON.stringify({
      pp_project_id: projectId,
      title: title,
      description: document.getElementById('csDescription').value.trim(),
    }),
  })
    .then(function (cs) {
      closeModal('createChangesetModal');
      showToast('Набор «' + cs.title + '» создан', 'success');
      activateChangeset(cs.id);
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
    });
}

// ══════════════════════════════════════════════════════════════════════════
//  Активация набора
// ══════════════════════════════════════════════════════════════════════════

function activateChangeset(id) {
  closeModal('changesetListModal');

  fetchJson('/api/changesets/' + id + '/')
    .then(function (cs) {
      currentChangesetId = cs.id;
      currentChangeset = cs;
      sandboxMode = true;

      // UI баннер
      var panel = document.getElementById('sandboxPanel');
      panel.style.display = 'block';
      document.getElementById('sandboxBannerTitle').textContent = cs.title;

      var badge = document.getElementById('sandboxStatusBadge');
      badge.textContent = cs.status_display;
      badge.className = 'sandbox-badge ' + cs.status;

      var config = _getSbConfig();

      // Показать/скрыть кнопки по статусу
      var isDraft = cs.status === 'draft';
      var isReview = cs.status === 'review';
      var canApprove = config.canApprove || config.isAdmin;

      _showEl('sandboxSubmitBtn', isDraft && cs.items_count > 0);
      _showEl('sandboxApproveBtn', isReview && canApprove);
      _showEl('sandboxRejectBtn', isReview && canApprove);
      _showEl('sandboxDiffBtn', cs.items_count > 0);

      var btn = document.getElementById('sandboxToggleBtn');
      if (btn) btn.classList.add('active');
      var label = document.getElementById('sandboxToggleLabel');
      if (label) label.textContent = 'Песочница ✓';

      // Визуальный режим песочницы на таблице
      var pv = document.getElementById('projectView');
      if (pv) pv.classList.add('sandbox-active');

      // Бегущая полоса вверху экрана
      var indicator = document.getElementById('sandboxTopbarIndicator');
      if (indicator) indicator.classList.add('active');

      // Подсветим строки в таблице
      _applySandboxOverlay(cs.items || []);

      showToast('Активирован набор «' + cs.title + '»', 'success');
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
    });
}

function _showEl(id, show) {
  var el = document.getElementById(id);
  if (el) el.style.display = show ? '' : 'none';
}

// ══════════════════════════════════════════════════════════════════════════
//  Overlay на строки таблицы
// ══════════════════════════════════════════════════════════════════════════

function _applySandboxOverlay(items) {
  // Очищаем предыдущие маркеры
  document.querySelectorAll('tr[data-sandbox-item]').forEach(function (el) {
    el.remove();
  });
  document
    .querySelectorAll('.sandbox-create,.sandbox-update,.sandbox-delete')
    .forEach(function (el) {
      el.classList.remove('sandbox-create', 'sandbox-update', 'sandbox-delete');
    });
  document.querySelectorAll('.sandbox-action-badge').forEach(function (el) {
    el.remove();
  });
  document.querySelectorAll('.sandbox-cell-changed').forEach(function (el) {
    el.classList.remove('sandbox-cell-changed');
  });

  if (!items || !items.length) return;

  // Сначала обрабатываем update/delete (для существующих строк)
  items.forEach(function (item) {
    if (item.action === 'create') return; // обработаем ниже

    var row = document.querySelector('tr[data-id="' + item.target_row_id + '"]');
    if (!row) return;

    if (item.action === 'update') {
      row.classList.add('sandbox-update');
      // Подсветим изменённые ячейки
      if (item.field_changes) {
        var changedFields = Object.keys(item.field_changes);
        changedFields.forEach(function (field) {
          var cell = _findCellByField(row, field);
          if (cell) {
            cell.classList.add('sandbox-cell-changed');
            // Тултип: какое поле и на что изменено
            var label = _fieldLabel(field);
            var newVal = item.field_changes[field];
            var oldVal = (item.original_data && item.original_data[field]) || '';
            cell.title = '✏ ' + label + ': ' + oldVal + ' → ' + newVal;
          }
        });
        // Бейдж с перечислением полей
        var fieldNames = changedFields.map(function (f) {
          return _fieldLabel(f);
        });
        _addActionBadge(row, 'update', '✏ ' + fieldNames.join(', '));
      } else {
        _addActionBadge(row, 'update', 'Изм.');
      }
    } else if (item.action === 'delete') {
      row.classList.add('sandbox-delete');
      _addActionBadge(row, 'delete', 'Удал.');
    }
  });

  // Теперь добавляем sandbox-create строки в начало таблицы
  var createItems = items.filter(function (item) {
    return item.action === 'create';
  });
  if (createItems.length > 0) {
    _renderSandboxCreateRows(createItems);
  }
}

/**
 * Находит ячейку <td> в строке по имени поля.
 * В PP-таблице ячейки содержат input[data-col="field"] или select[data-col="field"].
 */
function _findCellByField(row, field) {
  // Ищем input или select с data-col
  var input = row.querySelector('[data-col="' + field + '"]');
  if (input) {
    return input.closest('td') || input.parentElement;
  }
  // Фолбэк: td[data-field]
  var td = row.querySelector('td[data-field="' + field + '"]');
  if (td) return td;

  // Фолбэк по индексу столбца
  var ppCols = [
    'row_code',
    'work_order',
    'stage_num',
    'work_num',
    'work_designation',
    'work_name',
    'date_end',
    'sheets_a4',
    'norm',
    'coeff',
    'labor',
    'center',
    'dept',
    'sector_head',
    'executor',
    'task_type',
  ];
  var idx = ppCols.indexOf(field);
  if (idx >= 0) {
    // +1 потому что первый td — номер строки
    var cells = row.querySelectorAll('td');
    if (cells[idx + 1]) return cells[idx + 1];
  }
  return null;
}

/**
 * Возвращает человекочитаемое название поля.
 */
function _fieldLabel(field) {
  var labels = {
    row_code: 'Код',
    work_order: 'Наряд-заказ',
    stage_num: 'Этап',
    work_num: '№ работы',
    work_designation: 'Обозначение',
    work_name: 'Наименование',
    date_end: 'Срок',
    sheets_a4: 'Ф. А4',
    norm: 'Норматив',
    coeff: 'Коэфф',
    labor: 'Трудоёмкость',
    center: 'НТЦ',
    dept: 'Подразделение',
    sector_head: 'Нач. сектора',
    executor: 'Разработчик',
    task_type: 'Тип задачи',
  };
  return labels[field] || field;
}

function _addActionBadge(row, action, text) {
  var firstCell = row.querySelector('td');
  if (!firstCell) return;
  // Проверяем, нет ли уже бейджа
  if (firstCell.querySelector('.sandbox-action-badge')) return;
  var badge = document.createElement('span');
  badge.className = 'sandbox-action-badge ' + action;
  badge.textContent = text;
  firstCell.appendChild(badge);
}

/**
 * Рендерит sandbox-create строки в начало таблицы.
 * Каждая строка помечена классом sandbox-create и data-sandbox-item="id".
 */
function _renderSandboxCreateRows(createItems) {
  var tbody = document.getElementById('ppTableBody');
  if (!tbody) return;

  // Удаляем старые sandbox-create строки (от предыдущего рендера)
  tbody.querySelectorAll('tr[data-sandbox-item]').forEach(function (el) {
    el.remove();
  });

  // Определяем количество столбцов в таблице
  var firstRow = tbody.querySelector('tr');
  var colCount = firstRow ? firstRow.children.length : 20;

  // Названия полей для читаемого отображения
  var fieldLabels = {
    row_code: 'Код строки',
    work_order: 'Наряд-заказ',
    stage_num: '№ этапа',
    work_num: '№ работы',
    work_designation: 'Обозначение',
    work_name: 'Наименование',
    date_end: 'Срок',
    sheets_a4: 'Ф. А4',
    norm: 'Норматив',
    coeff: 'Коэфф',
    labor: 'Плановая',
    center: 'НТЦ',
    dept: 'Подразделение',
    sector_head: 'Отдел / Нач. сектора',
    executor: 'Разработчик',
    task_type: 'Тип задачи',
  };

  // PP_COLUMNS порядок (из production_plan.js)
  var ppCols = [
    'row_code',
    'work_order',
    'stage_num',
    'work_num',
    'work_designation',
    'work_name',
    'date_end',
    'sheets_a4',
    'norm',
    'coeff',
    'labor',
    'center',
    'dept',
    'sector_head',
    'executor',
    'task_type',
  ];

  var refRow = tbody.querySelector('tr:first-child');

  createItems.forEach(function (item, idx) {
    var tr = document.createElement('tr');
    tr.dataset.sandboxItem = item.id;
    tr.classList.add('sandbox-create');

    var fc = item.field_changes || {};
    var html = '';

    // Первый столбец — номер с бейджем «Нов.»
    html += '<td><span class="sandbox-action-badge create">Нов.</span></td>';

    // Строим ячейки по PP_COLUMNS, заполняя из field_changes
    for (var i = 0; i < ppCols.length; i++) {
      var col = ppCols[i];
      var val = fc[col] || '';
      html += '<td style="font-size:12px;padding:4px 6px;">' + esc(String(val)) + '</td>';
    }

    // Последний столбец — действия (кнопка удаления из песочницы)
    html +=
      '<td style="text-align:center;white-space:nowrap;">' +
      '<button class="btn-delete sandbox-remove-item" data-item-id="' +
      item.id +
      '" title="Удалить из песочницы">' +
      '<i class="fas fa-times"></i></button></td>';

    tr.innerHTML = html;

    // Вставляем в начало таблицы
    if (tbody.firstChild) {
      tbody.insertBefore(tr, tbody.firstChild);
    } else {
      tbody.appendChild(tr);
    }
  });

  // Навешиваем обработчики удаления sandbox-элемента
  tbody.querySelectorAll('.sandbox-remove-item').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var itemId = this.getAttribute('data-item-id');
      _removeSandboxItem(itemId);
    });
  });
}

/**
 * Удаляет элемент из набора изменений (DELETE /api/changeset_items/<pk>/).
 */
function _removeSandboxItem(itemId) {
  if (!currentChangesetId) return;
  if (currentChangeset && currentChangeset.status !== 'draft') {
    showToast('Набор не в статусе «Черновик»', 'warning');
    return;
  }
  fetchJson('/api/changeset_items/' + itemId + '/', {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCsrfToken() },
  })
    .then(function () {
      showToast('Элемент удалён из песочницы', 'success');
      activateChangeset(currentChangesetId);
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
    });
}

// ══════════════════════════════════════════════════════════════════════════
//  Добавление элемента в набор (вызывается из production_plan.js)
// ══════════════════════════════════════════════════════════════════════════

function addSandboxItem(action, targetRowId, fieldChanges) {
  if (!currentChangesetId) {
    showToast('Сначала активируйте набор изменений', 'warning');
    return Promise.reject(new Error('No active changeset'));
  }

  if (currentChangeset && currentChangeset.status !== 'draft') {
    showToast('Набор не в статусе «Черновик» — изменения невозможны', 'warning');
    return Promise.reject(new Error('Changeset not draft'));
  }

  return fetchJson('/api/changesets/' + currentChangesetId + '/items/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
    body: JSON.stringify({
      action: action,
      target_row_id: targetRowId || null,
      field_changes: fieldChanges || {},
    }),
  })
    .then(function (item) {
      showToast('Изменение добавлено в песочницу', 'success');
      // Обновляем overlay
      activateChangeset(currentChangesetId);
      return item;
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
      throw err;
    });
}

// ══════════════════════════════════════════════════════════════════════════
//  Workflow: submit / approve / reject / reopen
// ══════════════════════════════════════════════════════════════════════════

function submitChangeset() {
  if (!currentChangesetId) return;
  confirmDialog('Отправить набор «' + (currentChangeset?.title || '') + '» на согласование?')
    .then(function (ok) {
      if (!ok) return;
      return fetchJson('/api/changesets/' + currentChangesetId + '/submit/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
    })
    .then(function (cs) {
      if (!cs) return;
      showToast('Набор отправлен на согласование', 'success');
      activateChangeset(cs.id);
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
    });
}

function approveChangeset() {
  if (!currentChangesetId) return;
  confirmDialog(
    'Утвердить и применить все изменения набора «' + (currentChangeset?.title || '') + '»?',
  )
    .then(function (ok) {
      if (!ok) return;
      return fetchJson('/api/changesets/' + currentChangesetId + '/approve/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
    })
    .then(function (cs) {
      if (!cs) return;
      showToast('Набор утверждён! Изменения применены.', 'success');
      exitSandbox();
      // Перезагрузить таблицу с актуальными данными
      if (typeof loadPPRows === 'function') loadPPRows();
    })
    .catch(function (err) {
      if (err && err.conflicts) {
        showToast('Обнаружены конфликты — данные изменились', 'error');
        // Показать конфликты
        _showConflicts(err.conflicts);
      } else {
        showToast('Ошибка: ' + (err.message || String(err)), 'error');
      }
    });
}

function openRejectDialog() {
  document.getElementById('rejectComment').value = '';
  document.getElementById('rejectModal').classList.add('open');
}

function rejectChangeset() {
  if (!currentChangesetId) return;
  var comment = document.getElementById('rejectComment').value.trim();
  if (!comment) {
    showToast('Укажите причину отклонения', 'warning');
    return;
  }

  fetchJson('/api/changesets/' + currentChangesetId + '/reject/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
    body: JSON.stringify({ reject_comment: comment }),
  })
    .then(function (cs) {
      closeModal('rejectModal');
      showToast('Набор отклонён', 'success');
      activateChangeset(cs.id);
    })
    .catch(function (err) {
      showToast('Ошибка: ' + (err.message || String(err)), 'error');
    });
}

function _showConflicts(conflicts) {
  var html =
    '<div class="diff-summary" style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);">' +
    '<strong>⚠️ Конфликты (' +
    conflicts.length +
    '):</strong></div>';
  conflicts.forEach(function (c) {
    html +=
      '<div class="diff-section"><div class="diff-section-header" style="background:rgba(239,68,68,0.06);">' +
      'Строка #' +
      (c.target_row_id || c.item_id) +
      ' — поле «' +
      esc(c.field || c.error || '') +
      '»</div>' +
      '<div class="diff-field-row">' +
      '<span class="diff-field-name">Ожидалось</span><span class="diff-field-old">' +
      esc(String(c.expected || '')) +
      '</span>' +
      '</div><div class="diff-field-row">' +
      '<span class="diff-field-name">Сейчас</span><span class="diff-field-new">' +
      esc(String(c.actual || '')) +
      '</span>' +
      '</div></div>';
  });
  document.getElementById('changesetDiffBody').innerHTML = html;
  document.getElementById('changesetDiffModal').classList.add('open');
}

// ══════════════════════════════════════════════════════════════════════════
//  Diff
// ══════════════════════════════════════════════════════════════════════════

function showChangesetDiff() {
  if (!currentChangesetId) return;
  var body = document.getElementById('changesetDiffBody');
  body.innerHTML = '<div class="skeleton-row"></div><div class="skeleton-row"></div>';
  document.getElementById('changesetDiffModal').classList.add('open');

  fetchJson('/api/changesets/' + currentChangesetId + '/diff/')
    .then(function (data) {
      var diff = data.diff || [];
      var summary = data.summary || {};

      var html =
        '<div class="diff-summary">' +
        '<div class="diff-summary-item"><span class="diff-summary-count" style="color:var(--success);">' +
        (summary.creates || 0) +
        '</span> созданий</div>' +
        '<div class="diff-summary-item"><span class="diff-summary-count" style="color:var(--warning);">' +
        (summary.updates || 0) +
        '</span> изменений</div>' +
        '<div class="diff-summary-item"><span class="diff-summary-count" style="color:var(--danger);">' +
        (summary.deletes || 0) +
        '</span> удалений</div>' +
        '</div>';

      diff.forEach(function (item) {
        var actionClass =
          item.action === 'create' ? 'create' : item.action === 'delete' ? 'delete' : 'update';
        var icon = item.action === 'create' ? '➕' : item.action === 'delete' ? '🗑️' : '✏️';
        var title =
          item.action_display + (item.target_row_id ? ' #' + item.target_row_id : ' (новая)');

        html += '<div class="diff-section">';
        html +=
          '<div class="diff-section-header"><span class="sandbox-action-badge ' +
          actionClass +
          '">' +
          icon +
          ' ' +
          esc(title) +
          '</span></div>';

        if (item.action === 'create' && item.new_data) {
          Object.keys(item.new_data).forEach(function (field) {
            html +=
              '<div class="diff-field-row">' +
              '<span class="diff-field-name">' +
              esc(field) +
              '</span>' +
              '<span class="diff-field-new">' +
              esc(String(item.new_data[field] || '')) +
              '</span>' +
              '</div>';
          });
        } else if (item.action === 'update' && item.changes) {
          item.changes.forEach(function (c) {
            html +=
              '<div class="diff-field-row">' +
              '<span class="diff-field-name">' +
              esc(c.field) +
              '</span>' +
              '<span class="diff-field-old">' +
              esc(String(c.old ?? '')) +
              '</span>' +
              '<span class="diff-field-new">' +
              esc(String(c.new ?? '')) +
              '</span>' +
              (c.conflict ? '<span class="diff-field-conflict">⚠ Конфликт</span>' : '') +
              '</div>';
          });
        } else if (item.action === 'delete' && item.deleted_data) {
          html +=
            '<div class="diff-field-row"><span class="diff-field-name" style="color:var(--danger);">Удаляемая строка</span>' +
            '<span style="flex:1;font-size:12px;color:var(--muted);">' +
            esc(item.deleted_data.work_name || '') +
            ' / ' +
            esc(item.deleted_data.row_code || '') +
            '</span></div>';
        }

        html += '</div>';
      });

      if (!diff.length) {
        html += emptyStateHtml({ iconHtml: '📋', title: 'Нет изменений' });
      }

      body.innerHTML = html;

      // Footer с кнопками
      var footer = document.getElementById('changesetDiffFooter');
      footer.innerHTML = '';
      if (currentChangeset && currentChangeset.status === 'review' && _getSbConfig().canApprove) {
        footer.innerHTML =
          '<button class="btn btn-success btn-sm" onclick="closeModal(\'changesetDiffModal\');approveChangeset();"><i class="fas fa-check"></i> Утвердить</button>' +
          '<button class="btn btn-danger btn-sm" onclick="closeModal(\'changesetDiffModal\');openRejectDialog();"><i class="fas fa-times"></i> Отклонить</button>';
      }
    })
    .catch(function (err) {
      body.innerHTML =
        '<div class="alert alert-error">Ошибка: ' + esc(err.message || String(err)) + '</div>';
    });
}
