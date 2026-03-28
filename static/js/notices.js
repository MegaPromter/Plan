/**
 * Журнал извещений (ЖИ) — SPA-логика.
 * Конфигурация передаётся через <script id="page-config" type="application/json">.
 */

/* ── Конфигурация из Django-шаблона ──────────────────────────────────────── */

const _cfg = JSON.parse(document.getElementById('page-config').textContent);
const IS_WRITER   = _cfg.isWriter;
const IS_ADMIN    = _cfg.isAdmin;
const USER_ROLE   = _cfg.userRole;
const USER_DEPT   = _cfg.userDept;
const USER_SECTOR = _cfg.userSector;

/* ── Права ───────────────────────────────────────────────────────────────── */

// canModifyRow(), isFullAccess() — замыкания из utils.js
const _canModify = makeCanModify(_cfg);
const _isFullAccess = makeIsFullAccess(_cfg);

/* ── Skeleton-загрузка ─────────────────────────────────────────────── */
// skeletonRows() — в utils.js
// skeletonRows() — в utils.js

/* ── Переключатель плотности — initDensityToggle() в utils.js ─────── */

/* ── Ограничение даты выпуска — не позже сегодня ─────────────────────────── */
(function() {
  var today = new Date().toISOString().slice(0, 10);
  ['mf_date_issued', 'cl_date_issued'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.max = today;
  });
})();

/* ── Состояние ───────────────────────────────────────────────────────────── */

let jiData = [];
let jiMfFilters = {};
let editingId = null;
let closingId = null;

/* ── Мультифильтры (через createMultiFilter из utils.js) ─────────────── */

const JI_COLS = ['ii_pi','notice_number','subject','doc_designation',
                 'date_issued','date_expires','dept','sector','executor','description','status'];

function jiGetValues(col) {
  const vals = new Set();
  jiData.forEach(n => {
    const v = col === 'status' ? (n.status || '') : (n[col] || '');
    if (v) vals.add(v);
  });
  return [...vals].sort((a,b) => String(a).localeCompare(String(b), 'ru'));
}

const _jiMf = createMultiFilter({
  getValues: jiGetValues,
  onApply: function(col, btn, sel) {
    if (sel.size === 0) {
      delete jiMfFilters[col]; btn.textContent = '\u25BC'; btn.classList.remove('active');
    } else {
      jiMfFilters[col] = sel;
      btn.textContent = sel.size === 1 ? [...sel][0] : sel.size + ' выбрано';
      btn.classList.add('active');
    }
    renderTable();
  }
});
function jiToggleMf(btn) { _jiMf.toggle(btn); }

/* ── Загрузка данных ─────────────────────────────────────────────────────── */

async function loadJournal() {
  try {
    document.getElementById('jiBody').innerHTML = skeletonRows(8, 13);
    const r = await fetch('/api/journal/?per_page=500');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    jiData = await r.json();
    _jiInitSort();
    renderTable();
  } catch(e) {
    document.getElementById('jiBody').innerHTML =
      '<tr><td colspan="13" style="color:var(--danger);text-align:center;">Ошибка загрузки данных</td></tr>';
  }
}

/* ── Фильтрация ──────────────────────────────────────────────────────────── */

function applyFilters() {
  return jiData.filter(n => {
    for (const [col, sel] of Object.entries(jiMfFilters)) {
      if (!sel || sel.size === 0) continue;
      const cell = (n[col] || '');
      if (!sel.has(cell)) return false;
    }
    return true;
  });
}

/* ── Сортировка столбцов ─────────────────────────────────────────────────── */
var _jiSortState = { col: null, dir: 'asc' };

function _jiInitSort() {
    var thead = document.querySelector('#jiTable thead');
    if (!thead) return;
    thead.querySelectorAll('th[data-sort]').forEach(function(th) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', function(e) {
            if (e.target.classList.contains('mf-trigger')) return;
            toggleSort(_jiSortState, th.getAttribute('data-sort'));
            renderSortIndicators(thead, _jiSortState);
            renderTable();
        });
    });
    renderSortIndicators(thead, _jiSortState);
}

/* ── Infinite scroll: ленивая отрисовка ──────────────────────────────────── */

const JI_CHUNK = APP_CONFIG.chunkSize;
let _jiFiltered = [];
let _jiRenderedCount = 0;
let _jiScrollDispose = null;

function renderTable() {
  _jiFiltered = applyFilters();
  // Сортировка
  if (_jiSortState.col) {
    _jiFiltered = applySortToArray(_jiFiltered, _jiSortState, function(n, col) {
      return n[col] || '';
    });
  }
  _jiRenderedCount = 0;
  if (_jiScrollDispose) { _jiScrollDispose(); _jiScrollDispose = null; }

  const tbody = document.getElementById('jiBody');
  if (!_jiFiltered.length) {
    tbody.innerHTML = emptyStateHtml({icon:'fas fa-envelope-open', title:'Нет извещений', desc:'Попробуйте изменить фильтры или добавьте новое извещение', action: IS_ADMIN ? '<button class="btn btn-primary btn-sm" onclick="openAddModal()"><i class="fas fa-plus"></i> Новое извещение</button>' : '', colspan:13});
    document.getElementById('jiFooter').textContent = 'Записей: 0';
    return;
  }
  tbody.innerHTML = '';
  _jiAppendBatch(JI_CHUNK);
  _jiAttachScrollListener();

  document.getElementById('jiFooter').textContent =
    'Записей: ' + _jiFiltered.length + (_jiFiltered.length < jiData.length ? ' (из ' + jiData.length + ')' : '');
}

function _makeJiRow(n, idx) {
  const STATUS_LABELS = {
    active:     ['badge-active',    'Действует'],
    expired:    ['badge-expired',   'Просрочено'],
    closed_no:  ['badge-closed-no', 'Погашено без внесения'],
    closed_yes: ['badge-closed-yes','Погашено с внесением'],
  };
  const [badgeCls, badgeTxt] = STATUS_LABELS[n.status] || ['badge-closed-yes', n.status || '\u2014'];
  const statusBadge = '<span class="badge-sm ' + badgeCls + '">' + badgeTxt + '</span>';
  const autoTag = n.is_auto ? '<span class="badge-sm tt-auto" title="Запись создана на основании отчёта о выполненной работе">Авто</span>' : '<span class="badge-sm tt-manual" title="Запись создана вручную">Ручное</span>';
  const rowMod = _canModify(n.dept, n.sector);
  const canClose = rowMod && (n.status === 'active' || n.status === 'expired');
  const canEdit = rowMod && !n.is_auto;
  const canDel = _isFullAccess() && !n.is_auto;
  let actions = '<td class="col-actions" style="text-align:center;white-space:nowrap;">';
  if (canEdit) {
    actions += '<button class="ji-btn" onclick="openEditModal(' + n.id + ')" title="Редактировать">&#9998;</button> ';
  }
  actions += '<button class="ji-btn" onclick="openDescModal(' + n.id + ')" title="Описание">&#128221;</button> ';
  if (canClose) {
    actions += '<button class="ji-btn ji-btn-close" onclick="openCloseModal(' + n.id + ')" title="Погасить">&#9745;</button> ';
  }
  if (canDel) {
    actions += '<button class="ji-btn ji-btn-del" onclick="deleteRow(' + n.id + ')" title="Удалить">&#10005;</button>';
  }
  actions += '</td>';
  return '<tr>' +
    '<td style="color:var(--muted);font-size:12px;text-align:center;">' + (idx + 1) + '</td>' +
    '<td title="' + esc(n.ii_pi) + '">' + (esc(n.ii_pi) || '\u2014') + autoTag + '</td>' +
    '<td title="' + esc(n.notice_number) + '">' + (esc(n.notice_number) || '\u2014') + '</td>' +
    '<td title="' + esc(n.subject) + '">' + (esc(n.subject) || '\u2014') + '</td>' +
    '<td title="' + esc(n.doc_designation) + '">' + (esc(n.doc_designation) || '\u2014') + '</td>' +
    '<td>' + (esc(n.date_issued) || '\u2014') + '</td>' +
    '<td>' + (esc(n.date_expires) || '\u2014') + '</td>' +
    '<td title="' + esc(n.dept_name) + '">' + (esc(n.dept) || '\u2014') + '</td>' +
    '<td title="' + esc(n.sector) + '">' + (esc(n.sector) || '\u2014') + '</td>' +
    '<td title="' + esc(n.executor) + '">' + (esc(n.executor) || '\u2014') + '</td>' +
    '<td title="' + esc(n.description) + '">' + (esc(n.description) || '\u2014') + '</td>' +
    '<td>' + statusBadge + '</td>' +
    actions +
  '</tr>';
}

function _jiAppendBatch(count) {
  const tbody = document.getElementById('jiBody');
  const end = Math.min(_jiRenderedCount + count, _jiFiltered.length);
  const spinner = document.getElementById('jiScrollSpinner');
  if (spinner) spinner.remove();

  let html = '';
  for (let i = _jiRenderedCount; i < end; i++) {
    html += _makeJiRow(_jiFiltered[i], i);
  }
  tbody.insertAdjacentHTML('beforeend', html);
  _jiRenderedCount = end;

  if (_jiRenderedCount < _jiFiltered.length) {
    const spinnerTr = document.createElement('tr');
    spinnerTr.id = 'jiScrollSpinner';
    spinnerTr.innerHTML = '<td colspan="13" class="scroll-spinner"><i class="fas fa-spinner"></i> Загружено ' + _jiRenderedCount + ' из ' + _jiFiltered.length + '...</td>';
    tbody.appendChild(spinnerTr);
  }
}

function _jiAttachScrollListener() {
  if (_jiScrollDispose) { _jiScrollDispose(); _jiScrollDispose = null; }
  if (_jiRenderedCount >= _jiFiltered.length) return;

  _jiScrollDispose = createScrollLoader(
    document.querySelector('.ji-wrap'),
    () => {
      if (_jiRenderedCount < _jiFiltered.length) {
        _jiAppendBatch(JI_CHUNK);
        if (_jiRenderedCount >= _jiFiltered.length && _jiScrollDispose) {
          _jiScrollDispose(); _jiScrollDispose = null;
        }
      }
    },
    200
  );
}

// escapeHtml() — в utils.js (alias esc уже объявлен в utils.js через var)

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
  const iipi = document.getElementById('mf_ii_pi').value;
  const exp = document.getElementById('mf_date_expires');
  if (iipi === 'ИИ') {
    if (exp.value) _savedDateExpires = exp.value;
    exp.disabled = true;
    exp.value = '';
  } else {
    exp.disabled = false;
    if (!exp.value && _savedDateExpires) exp.value = _savedDateExpires;
  }
}

const _mfIiPiEl = document.getElementById('mf_ii_pi');
if (_mfIiPiEl) _mfIiPiEl.addEventListener('change', _updateExpiresDisabled);

function openAddModal() {
  editingId = null;
  document.getElementById('jiModalTitle').textContent = 'Добавить извещение';
  _fillModal({status: 'active'});
  document.getElementById('jiModal').classList.add('open');
}

function openEditModal(id) {
  const n = jiData.find(x => x.id === id);
  if (!n || n.is_auto) return;
  editingId = id;
  document.getElementById('jiModalTitle').textContent = 'Редактировать извещение';
  _fillModal(n);
  document.getElementById('jiModal').classList.add('open');
}

let descEditingId = null;

function openDescModal(id) {
  const n = jiData.find(x => x.id === id);
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
  const desc = document.getElementById('desc_text').value;
  try {
    const r = await fetch('/api/journal/' + descEditingId + '/', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken()},
      body: JSON.stringify({description: desc}),
    });
    if (r.ok) {
      const n = jiData.find(x => x.id === descEditingId);
      if (n) n.description = desc;
      closeDescModal();
      renderTable();
    } else {
      let d = {};
      try { d = await r.json(); } catch(_) {}
      showToast(d.error || 'Ошибка сохранения', 'error');
    }
  } catch(e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

function closeModal() {
  document.getElementById('jiModal').classList.remove('open');
}

async function saveModal() {
  const payload = {
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

  let url, method;
  if (editingId) {
    url = '/api/journal/' + editingId + '/';
    method = 'PUT';
  } else {
    url = '/api/journal/create/';
    method = 'POST';
  }

  try {
    const r = await fetch(url, {
      method,
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken()},
      body: JSON.stringify(payload),
    });
    let d = {};
    try { d = await r.json(); } catch(_) {}
    if (!r.ok) { showToast(d.error || 'Ошибка сохранения', 'error'); return; }
    closeModal();
    await loadJournal();
  } catch(e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

/* ── Модал погашения ─────────────────────────────────────────────────────── */

async function openCloseModal(id) {
  closingId = id;
  document.getElementById('cl_status').value = 'closed_yes';
  document.getElementById('cl_notice_number').value = '';
  document.getElementById('cl_date_issued').value = '';
  const sel = document.getElementById('cl_executor');
  sel.innerHTML = '<option value="">Загрузка...</option>';
  const notice = jiData.find(x => x.id === id);
  const deptCode = notice ? notice.dept : '';
  if (deptCode) {
    try {
      const r = await fetch('/api/dept_employees/?dept=' + encodeURIComponent(deptCode));
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const emps = await r.json();
      sel.innerHTML = '<option value="">— выберите —</option>';
      emps.forEach(function(emp) {
        const opt = document.createElement('option');
        opt.value = emp.short_name;
        opt.textContent = emp.short_name;
        sel.appendChild(opt);
      });
    } catch(e) {
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
  const cn = document.getElementById('cl_notice_number').value.trim();
  const cd = document.getElementById('cl_date_issued').value;
  const ce = document.getElementById('cl_executor').value.trim();
  if (!cn || !cd || !ce) {
    showToast('Заполните все обязательные поля', 'warning');
    return;
  }
  const payload = {
    status: document.getElementById('cl_status').value,
    closure_notice_number: cn,
    closure_date_issued: cd,
    closure_executor: ce,
  };
  try {
    const r = await fetch('/api/journal/' + closingId + '/', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken()},
      body: JSON.stringify(payload),
    });
    let d = {};
    try { d = await r.json(); } catch(_) {}
    if (!r.ok) { showToast(d.error || 'Ошибка погашения', 'error'); return; }
    closeCloseModal();
    await loadJournal();
  } catch(e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

/* ── Удаление ────────────────────────────────────────────────────────────── */

async function deleteRow(id) {
  const n = jiData.find(x => x.id === id);
  if (n && n.is_auto) { showToast('Автоматические записи нельзя удалить', 'warning'); return; }
  if (!await confirmDialog('Удалить запись?', 'Подтверждение')) return;
  try {
    const r = await fetch('/api/journal/' + id + '/', {
      method: 'DELETE',
      headers: {'X-CSRFToken': getCsrfToken()},
    });
    if (r.ok) {
      jiData = jiData.filter(x => x.id !== id);
      renderTable();
      showToast('Запись удалена', 'success');
    } else {
      let d = {};
      try { d = await r.json(); } catch(_) {}
      showToast(d.error || 'Ошибка удаления', 'error');
    }
  } catch(e) {
    showToast('Ошибка сети: ' + e.message, 'error');
  }
}

// getCsrfToken() удалён — используем getCsrfToken() из utils.js

/* ── Закрытие модалов по клику на оверлей — обрабатывается глобально в modal.js/base.js ── */

/* ── Инициализация ───────────────────────────────────────────────────────── */

initDensityToggle('.ji-wrap', (_cfg.colSettings && _cfg.colSettings.density) || 'comfortable');
loadJournal();

const JI_STATUS_LABELS = {active:'Действует', expired:'Просрочено', closed_no:'Погашено без внесения', closed_yes:'Погашено с внесением'};
buildExportDropdown('exportBtnContainer', {
  pageName: 'ЖИ',
  columns: [
    { key: 'ii_pi',           header: 'ИИ/ПИ',          width: 60 },
    { key: 'notice_number',   header: 'Номер изв.',      width: 120 },
    { key: 'subject',         header: 'Наименование',    width: 180 },
    { key: 'doc_designation', header: 'Обозначение',     width: 140 },
    { key: 'date_issued',     header: 'Дата выпуска',    width: 100 },
    { key: 'date_expires',    header: 'Срок действия',   width: 100 },
    { key: 'dept',            header: 'Отдел',           width: 70 },
    { key: 'sector',          header: 'Сектор',          width: 100 },
    { key: 'executor',        header: 'Разработчик',     width: 130 },
    { key: 'description',     header: 'Описание',        width: 200 },
    { key: 'status',          header: 'Статус',          width: 140, format: r => JI_STATUS_LABELS[r.status] || r.status },
  ],
  getAllData:      () => jiData,
  getFilteredData: () => applyFilters(),
});

/* Тултип для бейджей — используется нативный title (кастомный удалён) */
