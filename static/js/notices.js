/**
 * Журнал извещений (ЖИ) — SPA-логика.
 * Серверная пагинация + infinite scroll.
 * Конфигурация передаётся через <script id="page-config" type="application/json">.
 */

/* ── Конфигурация из Django-шаблона ──────────────────────────────────────── */

const _cfg = JSON.parse(document.getElementById('page-config').textContent);
const IS_WRITER = _cfg.isWriter;
const IS_ADMIN = _cfg.isAdmin;
const USER_ROLE = _cfg.userRole;
const USER_DEPT = _cfg.userDept;
const USER_SECTOR = _cfg.userSector;

/* ── Права ───────────────────────────────────────────────────────────────── */

const _canModify = makeCanModify(_cfg);
const _isFullAccess = makeIsFullAccess(_cfg);

/* ── Ограничение даты выпуска — не позже сегодня ─────────────────────────── */
(function () {
  var today = new Date().toISOString().slice(0, 10);
  ['mf_date_issued', 'cl_date_issued'].forEach(function (id) {
    var el = document.getElementById(id);
    if (el) el.max = today;
  });
})();

/* ── Состояние ───────────────────────────────────────────────────────────── */

let jiData = []; // загруженные строки (буфер, append-only)
let jiTotal = 0; // общее кол-во на сервере (с учётом фильтров)
let jiHasMore = false; // есть ли ещё строки на сервере
let jiLoading = false; // идёт ли загрузка сейчас

let jiMfFilters = {}; // col → Set (выбранные значения мульти-фильтров)
let jiFacets = {}; // col → [val, ...] (уникальные значения с сервера)
let editingId = null;
let closingId = null;

const JI_CHUNK = APP_CONFIG.chunkSize; // 50

/* ── Серверная сортировка ──────────────────────────────────────────────── */

var _jiSortState = { col: null, dir: 'asc' };

function _jiInitSort() {
  var thead = document.querySelector('#jiTable thead');
  if (!thead) return;
  thead.querySelectorAll('th[data-sort]').forEach(function (th) {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    th.addEventListener('click', function (e) {
      if (e.target.classList.contains('mf-trigger')) return;
      toggleSort(_jiSortState, th.getAttribute('data-sort'));
      renderSortIndicators(thead, _jiSortState);
      // Серверная сортировка: перезагрузить данные с offset=0
      loadJournal();
    });
  });
  renderSortIndicators(thead, _jiSortState);
}

/* ── Мультифильтры (через createMultiFilter из utils.js) ─────────────── */

const JI_COLS = [
  'ii_pi',
  'notice_number',
  'subject',
  'doc_designation',
  'date_issued',
  'date_expires',
  'dept',
  'sector',
  'executor',
  'description',
  'status',
];

/** Возвращает уникальные значения из серверных фасетов. */
function jiGetValues(col) {
  return jiFacets[col] || [];
}

const _jiMf = createMultiFilter({
  getValues: jiGetValues,
  onApply: function (col, btn, sel) {
    if (sel.size === 0) {
      delete jiMfFilters[col];
      btn.textContent = '\u25BC';
      btn.classList.remove('active');
    } else {
      jiMfFilters[col] = sel;
      btn.textContent = sel.size === 1 ? [...sel][0] : sel.size + ' выбрано';
      btn.classList.add('active');
    }
    // Серверная фильтрация: перезагрузить данные с offset=0
    loadJournal();
  },
});
function jiToggleMf(btn) {
  _jiMf.toggle(btn);
}

/* ── Построение query string ─────────────────────────────────────────── */

function _buildQueryParams(offset) {
  var params = new URLSearchParams();
  params.set('limit', JI_CHUNK);
  params.set('offset', offset);

  // Сортировка
  if (_jiSortState.col) {
    var prefix = _jiSortState.dir === 'desc' ? '-' : '';
    params.set('sort', prefix + _jiSortState.col);
  }

  // Мульти-фильтры
  for (var col in jiMfFilters) {
    var sel = jiMfFilters[col];
    if (sel && sel.size > 0) {
      sel.forEach(function (v) {
        params.append('mf_' + col, v);
      });
    }
  }

  return params.toString();
}

/* ── Загрузка данных ─────────────────────────────────────────────────────── */

async function loadJournal() {
  if (jiLoading) return;
  jiLoading = true;
  jiData = [];
  jiTotal = 0;
  jiHasMore = false;

  var tbody = document.getElementById('jiBody');
  tbody.innerHTML = skeletonRows(8, 13);

  // Загружаем фасеты и первую порцию параллельно
  try {
    var [facetsResp, dataResp] = await Promise.all([
      fetch('/api/journal/facets/'),
      fetch('/api/journal/?' + _buildQueryParams(0)),
    ]);

    if (facetsResp.ok) {
      jiFacets = await facetsResp.json();
    }

    if (!dataResp.ok) throw new Error('HTTP ' + dataResp.status);

    jiData = await dataResp.json();
    jiTotal = parseInt(dataResp.headers.get('X-Total-Count') || '0', 10);
    jiHasMore = dataResp.headers.get('X-Has-More') === 'true';
  } catch (e) {
    tbody.innerHTML =
      '<tr><td colspan="13" style="color:var(--danger);text-align:center;">Ошибка загрузки данных</td></tr>';
    jiLoading = false;
    return;
  }

  jiLoading = false;
  _jiInitSort();
  renderTable();
  _initJiColResize();
}

/* ── Ресайз колонок (общий модуль col_resize.js) ────────────────────────── */

let _jiColResizeInitialized = false;
function _initJiColResize() {
  const table = document.getElementById('jiTable');
  if (!table || !window.ColResize) return;
  // Применяем сохранённые ширины при каждом обновлении данных —
  // они хранятся в `col_settings` по ключам `journal_<col>`.
  window.ColResize.apply(table, _cfg.colSettings || {});
  if (_jiColResizeInitialized) return;
  window.ColResize.attach(table);
  _jiColResizeInitialized = true;
}

/** Дозагрузка следующей порции (при скролле вниз). */
async function loadMore() {
  if (jiLoading || !jiHasMore) return;
  jiLoading = true;

  try {
    var r = await fetch('/api/journal/?' + _buildQueryParams(jiData.length));
    if (!r.ok) throw new Error('HTTP ' + r.status);

    var batch = await r.json();
    jiTotal = parseInt(r.headers.get('X-Total-Count') || jiTotal, 10);
    jiHasMore = r.headers.get('X-Has-More') === 'true';

    // Добавляем в буфер и дорисовываем строки
    var startIdx = jiData.length;
    jiData = jiData.concat(batch);
    _jiAppendBatch(batch, startIdx);
    _updateFooter();

    // Если больше нет — снимаем слушатель скролла
    if (!jiHasMore && _jiScrollDispose) {
      _jiScrollDispose();
      _jiScrollDispose = null;
    }
  } catch (e) {
    showToast('Ошибка загрузки: ' + e.message, 'error');
  }

  jiLoading = false;
}

/* ── Отрисовка таблицы ──────────────────────────────────────────────────── */

let _jiScrollDispose = null;

function renderTable() {
  if (_jiScrollDispose) {
    _jiScrollDispose();
    _jiScrollDispose = null;
  }

  var tbody = document.getElementById('jiBody');
  if (!jiData.length) {
    var hasFilters = Object.keys(jiMfFilters).length > 0;
    if (hasFilters) {
      tbody.innerHTML = emptyStateHtml({
        icon: 'fas fa-search',
        title: 'Ничего не найдено',
        desc: 'Попробуйте изменить фильтры или сбросить поиск',
        action: IS_ADMIN
          ? '<button class="btn btn-primary btn-sm" onclick="openAddModal()"><i class="fas fa-plus"></i> Новое извещение</button>'
          : '',
        colspan: 13,
      });
    } else {
      tbody.innerHTML = emptyStateHtml({
        icon: 'fas fa-file-alt',
        title: 'Нет извещений',
        desc: 'Журнал извещений пока пуст',
        action: IS_ADMIN
          ? '<button class="btn btn-primary btn-sm" onclick="openAddModal()"><i class="fas fa-plus"></i> Новое извещение</button>'
          : '',
        colspan: 13,
      });
    }
    _updateFooter();
    return;
  }

  tbody.innerHTML = '';
  // Отрисовываем все загруженные строки
  _jiAppendBatch(jiData, 0);
  _jiAttachScrollListener();
  _updateFooter();
}

function _updateFooter() {
  var footer = document.getElementById('jiFooter');
  if (!footer) return;
  if (jiTotal === 0) {
    footer.textContent = 'Записей: 0';
  } else {
    footer.textContent = 'Загружено: ' + jiData.length + ' из ' + jiTotal;
  }
}

function _makeJiRow(n, idx) {
  var STATUS_LABELS = {
    active: ['badge-active', 'Действует'],
    expired: ['badge-expired', 'Просрочено'],
    closed_no: ['badge-closed-no', 'Погашено без внесения'],
    closed_yes: ['badge-closed-yes', 'Погашено с внесением'],
  };
  var ref = STATUS_LABELS[n.status] || ['badge-closed-yes', n.status || '\u2014'];
  var badgeCls = ref[0],
    badgeTxt = ref[1];
  var statusBadge = '<span class="badge-sm ' + badgeCls + '">' + badgeTxt + '</span>';
  var autoTag = n.is_auto
    ? '<span class="badge-sm tt-auto" title="Запись создана на основании отчёта о выполненной работе">Авто</span>'
    : '<span class="badge-sm tt-manual" title="Запись создана вручную">Ручное</span>';
  var rowMod = _canModify(n.dept, n.sector);
  var canClose = rowMod && (n.status === 'active' || n.status === 'expired');
  var canEdit = rowMod && !n.is_auto;
  var canDel = _isFullAccess() && !n.is_auto;
  var actions = '<td class="col-actions" style="text-align:center;white-space:nowrap;">';
  if (canEdit) {
    actions +=
      '<button class="ji-btn" onclick="openEditModal(' +
      n.id +
      ')" title="Редактировать">&#9998;</button> ';
  }
  actions +=
    '<button class="ji-btn" onclick="openDescModal(' +
    n.id +
    ')" title="Описание">&#128221;</button> ';
  if (canClose) {
    actions +=
      '<button class="ji-btn ji-btn-close" onclick="openCloseModal(' +
      n.id +
      ')" title="Погасить">&#9745;</button> ';
  }
  if (canDel) {
    actions +=
      '<button class="ji-btn ji-btn-del" onclick="deleteRow(' +
      n.id +
      ')" title="Удалить">&#10005;</button>';
  }
  actions += '</td>';
  return (
    '<tr>' +
    '<td style="color:var(--muted);text-align:center;">' +
    (idx + 1) +
    '</td>' +
    '<td title="' +
    esc(n.ii_pi) +
    '">' +
    (esc(n.ii_pi) || '\u2014') +
    autoTag +
    '</td>' +
    '<td title="' +
    esc(n.notice_number) +
    '">' +
    (esc(n.notice_number) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.subject) +
    '">' +
    (esc(n.subject) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.doc_designation) +
    '">' +
    (esc(n.doc_designation) || '\u2014') +
    '</td>' +
    '<td>' +
    (esc(n.date_issued) || '\u2014') +
    '</td>' +
    '<td>' +
    (esc(n.date_expires) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.dept_name) +
    '">' +
    (esc(n.dept) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.sector) +
    '">' +
    (esc(n.sector) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.executor) +
    '">' +
    (esc(n.executor) || '\u2014') +
    '</td>' +
    '<td title="' +
    esc(n.description) +
    '">' +
    (esc(n.description) || '\u2014') +
    '</td>' +
    '<td>' +
    statusBadge +
    '</td>' +
    actions +
    '</tr>'
  );
}

function _jiAppendBatch(batch, startIdx) {
  var tbody = document.getElementById('jiBody');
  // Убираем спиннер если есть
  var spinner = document.getElementById('jiScrollSpinner');
  if (spinner) spinner.remove();

  var html = '';
  for (var i = 0; i < batch.length; i++) {
    html += _makeJiRow(batch[i], startIdx + i);
  }
  tbody.insertAdjacentHTML('beforeend', html);

  // Показываем спиннер если ещё есть данные на сервере
  if (jiHasMore) {
    var spinnerTr = document.createElement('tr');
    spinnerTr.id = 'jiScrollSpinner';
    spinnerTr.innerHTML =
      '<td colspan="13" class="scroll-spinner"><i class="fas fa-spinner"></i> Загружено ' +
      jiData.length +
      ' из ' +
      jiTotal +
      '...</td>';
    tbody.appendChild(spinnerTr);
  }
}

function _jiAttachScrollListener() {
  if (_jiScrollDispose) {
    _jiScrollDispose();
    _jiScrollDispose = null;
  }
  if (!jiHasMore) return;

  _jiScrollDispose = createScrollLoader(
    document.querySelector('.ji-wrap'),
    function () {
      if (!jiLoading && jiHasMore) {
        loadMore();
      }
    },
    200,
  );
}

/* ── Модал добавления/редактирования ─────────────────────────────────────── */

function _fillModal(n) {
  document.getElementById('mf_ii_pi').value = n.ii_pi || '';
  document.getElementById('mf_notice_number').value = n.notice_number || '';
  document.getElementById('mf_date_issued').value = n.date_issued || '';
  document.getElementById('mf_date_expires').value = n.date_expires || '';
  document.getElementById('mf_dept').value = n.dept || '';
  document.getElementById('mf_sector').value = n.sector || '';
  document.getElementById('mf_executor').value = n.executor || '';
  document.getElementById('mf_subject').value = n.subject || '';
  document.getElementById('mf_doc_designation').value = n.doc_designation || '';
  document.getElementById('mf_description').value = n.description || '';
  document.getElementById('mf_status').value = n.status_raw || n.status || 'active';
  _updateExpiresDisabled();
}

let _savedDateExpires = '';
function _updateExpiresDisabled() {
  var iipi = document.getElementById('mf_ii_pi').value;
  var exp = document.getElementById('mf_date_expires');
  if (iipi === 'ИИ') {
    if (exp.value) _savedDateExpires = exp.value;
    exp.disabled = true;
    exp.value = '';
  } else {
    exp.disabled = false;
    if (!exp.value && _savedDateExpires) exp.value = _savedDateExpires;
  }
}

var _mfIiPiEl = document.getElementById('mf_ii_pi');
if (_mfIiPiEl) _mfIiPiEl.addEventListener('change', _updateExpiresDisabled);

function openAddModal() {
  editingId = null;
  document.getElementById('jiModalTitle').textContent = 'Добавить извещение';
  _fillModal({ status: 'active' });
  document.getElementById('jiModal').classList.add('open');
}

function openEditModal(id) {
  var n = jiData.find(function (x) {
    return x.id === id;
  });
  if (!n || n.is_auto) return;
  editingId = id;
  document.getElementById('jiModalTitle').textContent = 'Редактировать извещение';
  _fillModal(n);
  document.getElementById('jiModal').classList.add('open');
}

let descEditingId = null;

function openDescModal(id) {
  var n = jiData.find(function (x) {
    return x.id === id;
  });
  if (!n) return;
  descEditingId = id;
  document.getElementById('desc_text').value = n.description || '';
  document.getElementById('jiDescModal').classList.add('open');
}

function closeDescModal() {
  document.getElementById('jiDescModal').classList.remove('open');
  descEditingId = null;
}

async function saveDescModal() {
  if (!descEditingId) return;
  var desc = document.getElementById('desc_text').value;
  try {
    var r = await fetch('/api/journal/' + descEditingId + '/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ description: desc }),
    });
    if (r.ok) {
      // Обновляем в локальном буфере
      var n = jiData.find(function (x) {
        return x.id === descEditingId;
      });
      if (n) n.description = desc;
      closeDescModal();
      renderTable();
    } else {
      var d = {};
      try {
        d = await r.json();
      } catch (_) {
        /* ignored */
      }
      showToast(d.error || 'Ошибка сохранения', 'error');
    }
  } catch (e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

function closeModal() {
  document.getElementById('jiModal').classList.remove('open');
}

async function saveModal() {
  var payload = {
    ii_pi: document.getElementById('mf_ii_pi').value,
    notice_number: document.getElementById('mf_notice_number').value,
    date_issued: document.getElementById('mf_date_issued').value || null,
    date_expires: document.getElementById('mf_date_expires').value || null,
    dept: document.getElementById('mf_dept').value,
    sector: document.getElementById('mf_sector').value,
    executor: document.getElementById('mf_executor').value,
    subject: document.getElementById('mf_subject').value,
    doc_designation: document.getElementById('mf_doc_designation').value,
    description: document.getElementById('mf_description').value,
    status: document.getElementById('mf_status').value,
  };

  var url, method;
  if (editingId) {
    url = '/api/journal/' + editingId + '/';
    method = 'PUT';
  } else {
    url = '/api/journal/create/';
    method = 'POST';
  }

  try {
    var r = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    var d = {};
    try {
      d = await r.json();
    } catch (_) {
      /* ignored */
    }
    if (!r.ok) {
      showToast(d.error || 'Ошибка сохранения', 'error');
      return;
    }
    closeModal();
    // После создания/редактирования — полная перезагрузка (фасеты могут измениться)
    await loadJournal();
  } catch (e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

/* ── Модал погашения ─────────────────────────────────────────────────────── */

async function openCloseModal(id) {
  closingId = id;
  document.getElementById('cl_status').value = 'closed_yes';
  document.getElementById('cl_notice_number').value = '';
  document.getElementById('cl_date_issued').value = '';
  var sel = document.getElementById('cl_executor');
  sel.innerHTML = '<option value="">Загрузка...</option>';
  var notice = jiData.find(function (x) {
    return x.id === id;
  });
  var deptCode = notice ? notice.dept : '';
  if (deptCode) {
    try {
      var r = await fetch('/api/dept_employees/?dept=' + encodeURIComponent(deptCode));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var emps = await r.json();
      sel.innerHTML = '<option value="">— выберите —</option>';
      emps.forEach(function (emp) {
        var opt = document.createElement('option');
        opt.value = emp.short_name;
        opt.textContent = emp.short_name;
        sel.appendChild(opt);
      });
    } catch (e) {
      sel.innerHTML = '<option value="">Ошибка загрузки</option>';
    }
  } else {
    sel.innerHTML = '<option value="">— нет отдела —</option>';
  }
  document.getElementById('jiCloseModal').classList.add('open');
}

function closeCloseModal() {
  document.getElementById('jiCloseModal').classList.remove('open');
  closingId = null;
}

async function saveCloseModal() {
  var cn = document.getElementById('cl_notice_number').value.trim();
  var cd = document.getElementById('cl_date_issued').value;
  var ce = document.getElementById('cl_executor').value.trim();
  if (!cn || !cd || !ce) {
    showToast('Заполните все обязательные поля', 'warning');
    return;
  }
  var payload = {
    status: document.getElementById('cl_status').value,
    closure_notice_number: cn,
    closure_date_issued: cd,
    closure_executor: ce,
  };
  try {
    var r = await fetch('/api/journal/' + closingId + '/', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(payload),
    });
    var d = {};
    try {
      d = await r.json();
    } catch (_) {
      /* ignored */
    }
    if (!r.ok) {
      showToast(d.error || 'Ошибка погашения', 'error');
      return;
    }
    closeCloseModal();
    await loadJournal();
  } catch (e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

/* ── Удаление ────────────────────────────────────────────────────────────── */

async function deleteRow(id) {
  var n = jiData.find(function (x) {
    return x.id === id;
  });
  if (n && n.is_auto) {
    showToast('Автоматические записи нельзя удалить', 'warning');
    return;
  }
  if (!(await confirmDialog('Удалить запись?', 'Подтверждение'))) return;
  try {
    var r = await fetch('/api/journal/' + id + '/', {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (r.ok) {
      showToast('Запись удалена', 'success');
      // Перезагружаем с сервера (счётчики и фасеты могут измениться)
      await loadJournal();
    } else {
      var d = {};
      try {
        d = await r.json();
      } catch (_) {
        /* ignored */
      }
      showToast(d.error || 'Ошибка удаления', 'error');
    }
  } catch (e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

/* ── Инициализация ───────────────────────────────────────────────────────── */

initDensityToggle('.ji-wrap', (_cfg.colSettings && _cfg.colSettings.density) || 'comfortable');
loadJournal();

var JI_STATUS_LABELS = {
  active: 'Действует',
  expired: 'Просрочено',
  closed_no: 'Погашено без внесения',
  closed_yes: 'Погашено с внесением',
};
buildExportDropdown('exportBtnContainer', {
  pageName: 'ЖИ',
  columns: [
    { key: 'ii_pi', header: 'ИИ/ПИ', width: 60 },
    { key: 'notice_number', header: 'Номер изв.', width: 120 },
    { key: 'subject', header: 'Наименование', width: 180 },
    { key: 'doc_designation', header: 'Обозначение', width: 140 },
    { key: 'date_issued', header: 'Дата выпуска', width: 100 },
    { key: 'date_expires', header: 'Срок действия', width: 100 },
    { key: 'dept', header: 'Отдел', width: 70 },
    { key: 'sector', header: 'Сектор', width: 100 },
    { key: 'executor', header: 'Разработчик', width: 130 },
    { key: 'description', header: 'Описание', width: 200 },
    {
      key: 'status',
      header: 'Статус',
      width: 140,
      format: function (r) {
        return JI_STATUS_LABELS[r.status] || r.status;
      },
    },
  ],
  getAllData: function () {
    return jiData;
  },
  getFilteredData: function () {
    return jiData;
  },
});
