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

function _canModify(rowDept, rowSector) {
  if (!IS_WRITER) return false;
  if (IS_ADMIN || USER_ROLE === 'ntc_head' || USER_ROLE === 'ntc_deputy') return true;
  if (USER_ROLE === 'sector_head') return !!rowSector && rowSector === USER_SECTOR;
  return !!rowDept && rowDept === USER_DEPT;
}

function _isFullAccess() {
  return IS_ADMIN || USER_ROLE === 'ntc_head' || USER_ROLE === 'ntc_deputy';
}

/* ── Skeleton-загрузка ─────────────────────────────────────────────── */
function _jiSkeletonRows(count, cols) {
  let html = '';
  for (let i = 0; i < count; i++) {
    html += '<tr>';
    for (let c = 0; c < cols; c++) {
      const w = c === 0 ? 'sk-id' : (c < 3 ? 'sk-text' : (c % 3 === 0 ? 'sk-text-sm' : 'sk-text-md'));
      html += '<td><span class="skeleton ' + w + '" style="animation-delay:' + (i * 0.08) + 's"></span></td>';
    }
    html += '</tr>';
  }
  return html;
}

/* ── Переключатель плотности ───────────────────────────────────────── */
function _initJiDensity() {
  const wrap = document.querySelector('.ji-wrap');
  if (!wrap) return;
  const saved = (_cfg.colSettings && _cfg.colSettings.density) || 'comfortable';
  if (saved !== 'comfortable') wrap.classList.add('density-' + saved);
  const toggle = document.getElementById('densityToggle');
  if (!toggle) return;
  toggle.querySelectorAll('button').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.density === saved);
    btn.addEventListener('click', function() {
      const d = this.dataset.density;
      wrap.classList.remove('density-compact', 'density-comfortable', 'density-spacious');
      if (d !== 'comfortable') wrap.classList.add('density-' + d);
      toggle.querySelectorAll('button').forEach(function(b) { b.classList.toggle('active', b.dataset.density === d); });
      fetch('/api/col_settings/', {
        method: 'POST',
        headers: {'Content-Type':'application/json','X-CSRFToken': getCsrf()},
        body: JSON.stringify({ density: d })
      }).catch(function() {});
    });
  });
}

/* ── Состояние ───────────────────────────────────────────────────────────── */

let jiData = [];
let jiMfSelections = {};
let jiMfFilters = {};
let jiActiveDrop = null;
let jiActiveBtn = null;
let editingId = null;
let closingId = null;

/* ── Мультифильтры ───────────────────────────────────────────────────────── */

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

function jiBuildDrop(btn, col) {
  if (jiActiveDrop) jiActiveDrop.remove();
  const vals = jiGetValues(col);
  const selected = jiMfSelections[col] || new Set();
  const drop = document.createElement('div');
  drop.className = 'mf-dropdown open';
  drop.dataset.col = col;

  const sw = document.createElement('div'); sw.className = 'mf-search';
  const si = document.createElement('input'); si.placeholder = 'Поиск...'; si.autocomplete = 'off';
  si.oninput = () => {
    const q = si.value.toLowerCase();
    drop.querySelectorAll('.mf-option').forEach(o => {
      o.style.display = o.dataset.val.toLowerCase().includes(q) ? '' : 'none';
    });
  };
  sw.appendChild(si); drop.appendChild(sw);

  const ac = document.createElement('div'); ac.className = 'mf-actions';
  const selAll = document.createElement('button'); selAll.className = 'mf-btn'; selAll.textContent = 'Все';
  selAll.onclick = e => { e.stopPropagation(); jiMfSelections[col] = new Set(vals);
    drop.querySelectorAll('.mf-option input').forEach(c => c.checked = true); jiApplyMf(col, btn); };
  const clr = document.createElement('button'); clr.className = 'mf-btn'; clr.textContent = 'Сброс';
  clr.onclick = e => { e.stopPropagation(); jiMfSelections[col] = new Set();
    drop.querySelectorAll('.mf-option input').forEach(c => c.checked = false); jiApplyMf(col, btn); };
  ac.appendChild(selAll); ac.appendChild(clr); drop.appendChild(ac);

  vals.forEach(val => {
    const opt = document.createElement('div'); opt.className = 'mf-option'; opt.dataset.val = val;
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = selected.has(val);
    const toggle = () => {
      cb.checked = !cb.checked;
      const s = jiMfSelections[col] || new Set();
      cb.checked ? s.add(val) : s.delete(val);
      jiMfSelections[col] = s; jiApplyMf(col, btn);
    };
    cb.onchange = () => {
      const s = jiMfSelections[col] || new Set();
      cb.checked ? s.add(val) : s.delete(val);
      jiMfSelections[col] = s; jiApplyMf(col, btn);
    };
    opt.onclick = e => { if (e.target !== cb) toggle(); };
    opt.appendChild(cb); opt.appendChild(document.createTextNode(val)); drop.appendChild(opt);
  });

  document.body.appendChild(drop);
  const rect = btn.getBoundingClientRect();
  drop.style.top = (rect.bottom + 2) + 'px';
  drop.style.left = Math.min(rect.left, window.innerWidth - 270) + 'px';
  jiActiveDrop = drop; jiActiveBtn = btn;
  setTimeout(() => si.focus(), 50);
}

function jiToggleMf(btn) {
  if (jiActiveDrop && jiActiveBtn === btn) {
    jiActiveDrop.remove(); jiActiveDrop = null; jiActiveBtn = null; return;
  }
  jiBuildDrop(btn, btn.dataset.col);
}

function jiApplyMf(col, btn) {
  const sel = jiMfSelections[col] || new Set();
  if (sel.size === 0) {
    delete jiMfFilters[col]; btn.textContent = '\u25BC'; btn.classList.remove('active');
  } else {
    jiMfFilters[col] = sel;
    btn.textContent = sel.size === 1 ? [...sel][0] : sel.size + ' выбрано';
    btn.classList.add('active');
  }
  renderTable();
}

document.addEventListener('click', e => {
  if (jiActiveDrop && !jiActiveDrop.contains(e.target) && e.target !== jiActiveBtn) {
    jiActiveDrop.remove(); jiActiveDrop = null; jiActiveBtn = null;
  }
}, true);

/* ── Загрузка данных ─────────────────────────────────────────────────────── */

async function loadJournal() {
  try {
    document.getElementById('jiBody').innerHTML = _jiSkeletonRows(8, 13);
    const r = await fetch('/api/journal/?per_page=100000');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    jiData = await r.json();
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

/* ── Infinite scroll: ленивая отрисовка ──────────────────────────────────── */

const JI_CHUNK = 50;
let _jiFiltered = [];
let _jiRenderedCount = 0;
let _jiScrollDispose = null;

function renderTable() {
  _jiFiltered = applyFilters();
  _jiRenderedCount = 0;
  if (_jiScrollDispose) { _jiScrollDispose(); _jiScrollDispose = null; }

  const tbody = document.getElementById('jiBody');
  if (!_jiFiltered.length) {
    tbody.innerHTML = '<tr><td colspan="13" style="text-align:center;color:var(--muted);padding:20px;">Нет данных</td></tr>';
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
    spinnerTr.innerHTML = '<td colspan="13" class="scroll-spinner"><i class="fas fa-spinner"></i> Загрузка...</td>';
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

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
const esc = escapeHtml;

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
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
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
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
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
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCsrf()},
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
      headers: {'X-CSRFToken': getCsrf()},
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

function getCsrf() {
  return document.cookie.split(';').map(c => c.trim())
    .find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
}

/* ── Закрытие модалов по клику на оверлей ────────────────────────────────── */

document.getElementById('jiModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeModal();
});
document.getElementById('jiCloseModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeCloseModal();
});
document.getElementById('jiDescModal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeDescModal();
});

/* ── Инициализация ───────────────────────────────────────────────────────── */

_initJiDensity();
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
