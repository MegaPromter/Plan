/* ── Enterprise SPA ────────────────────────────────────────────────────── */
'use strict';

const CSRF = document.querySelector('[name=csrfmiddlewaretoken]').value;
const API  = '/api/enterprise';

// ── Состояние ────────────────────────────────────────────────────────────
let portfolioData  = [];
let projectsList   = []; // для селектов ГГ/Сквозной
let currentGG      = null;
let currentCross   = null;

// ── Утилиты ──────────────────────────────────────────────────────────────

function fetchJSON(url, opts) {
  const defaults = {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': CSRF,
    },
    credentials: 'same-origin',
  };
  return fetch(url, { ...defaults, ...opts }).then(r => {
    if (!r.ok) return r.json().then(d => Promise.reject(d));
    return r.json();
  });
}

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function openModal(id) {
  document.getElementById(id).classList.add('open');
}
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// ── Список сотрудников для селектов ГК ──────────────────────────────────

function populateChiefSelects() {
  ['createProjectChief', 'editProjectChief'].forEach(selId => {
    const sel = document.getElementById(selId);
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = '<option value="">—</option>' +
      (typeof EMPLOYEES !== 'undefined' ? EMPLOYEES : []).map(e =>
        `<option value="${e.id}">${escapeHtml(e.name)}</option>`
      ).join('');
    if (cur) sel.value = cur;
  });
}

// ── Статусы / приоритеты ─────────────────────────────────────────────────

const STATUS_LABELS = {
  prospective: 'Перспективный',
  approved:    'Утверждён',
  active:      'Активный',
  suspended:   'Приостановлен',
  deferred:    'Отложен',
  closed:      'Закрыт',
  cancelled:   'Отменён',
};

const PRIORITY_LABELS = {
  critical: 'Критический',
  high:     'Высокий',
  medium:   'Средний',
  low:      'Низкий',
};

function statusBadge(status) {
  const label = STATUS_LABELS[status] || status || '—';
  return `<span class="status-badge status-badge--${status}">${escapeHtml(label)}</span>`;
}

function priorityBadge(cat) {
  if (!cat) return '—';
  const label = PRIORITY_LABELS[cat] || cat;
  return `<span class="priority-badge priority-badge--${cat}">${escapeHtml(label)}</span>`;
}

// ── Табы ─────────────────────────────────────────────────────────────────

function initTabs() {
  const tabs = document.querySelectorAll('.ent-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
      tab.classList.add('active');
      tab.setAttribute('aria-selected', 'true');

      const target = tab.dataset.tab;
      document.querySelectorAll('.ent-panel').forEach(p => p.style.display = 'none');
      document.getElementById('panel-' + target).style.display = '';

      // Загружаем данные при первом переключении
      if (target === 'capacity') loadCapacity();
    });
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  ПОРТФЕЛЬ
// ══════════════════════════════════════════════════════════════════════════

// Порядок приоритетов для сортировки (меньше = важнее)
const PRIORITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

// ── Мультифильтры (общая утилита createMultiFilter из utils.js) ──────────
let pfMfFilters = {};

function pfGetValues(col) {
  const vals = new Set();
  portfolioData.forEach(p => {
    let v = '';
    if (col === 'name') v = p.name_full || p.name_short || '';
    else if (col === 'code') v = p.code || '';
    else if (col === 'status') v = STATUS_LABELS[p.status] || p.status || '';
    else if (col === 'priority_category') v = PRIORITY_LABELS[p.priority_category] || '';
    else if (col === 'chief') v = p.chief_designer ? p.chief_designer.name : '';
    if (v) vals.add(v);
  });
  return [...vals].sort((a, b) => String(a).localeCompare(String(b), 'ru'));
}

const _pfMf = createMultiFilter({
  getValues: pfGetValues,
  onApply: function(col, btn, sel) {
    if (sel.size === 0) {
      delete pfMfFilters[col]; btn.textContent = '▼'; btn.classList.remove('active');
    } else {
      pfMfFilters[col] = sel;
      btn.textContent = sel.size === 1 ? [...sel][0] : sel.size + ' выбрано';
      btn.classList.add('active');
    }
    pfUpdateBadge();
    renderPortfolio();
  }
});
function pfToggleMf(btn) { _pfMf.toggle(btn); }

function pfClearAll() {
  pfMfFilters = {};
  _pfMf.setSelections({});
  document.querySelectorAll('#portfolioTable .mf-trigger').forEach(b => {
    b.textContent = '▼'; b.classList.remove('active');
  });
  pfUpdateBadge();
  renderPortfolio();
}

function pfUpdateBadge() {
  const badge = document.getElementById('pfFiltersBadge');
  if (badge) badge.style.display = Object.keys(pfMfFilters).length ? 'inline' : 'none';
}

// ── Сортировка (общие утилиты из utils.js) ──────────────────────────────
// По умолчанию сортируем по приоритету
let _pfSortState = { col: 'priority', dir: 'asc' };

function pfGetSortVal(p, col) {
  if (col === 'name') return (p.name_full || p.name_short || '').toLowerCase();
  if (col === 'code') return (p.code || '').toLowerCase();
  if (col === 'status') return STATUS_LABELS[p.status] || p.status || '';
  if (col === 'priority') {
    // Сначала по категории (critical=0..low=3), потом по номеру
    const cat = PRIORITY_ORDER[p.priority_category] != null ? PRIORITY_ORDER[p.priority_category] : 99;
    const num = p.priority_number != null ? p.priority_number : 9999;
    return cat * 10000 + num;
  }
  if (col === 'chief') return p.chief_designer ? p.chief_designer.name.toLowerCase() : '';
  if (col === 'pp_count') return p.pp_count || 0;
  if (col === 'sp_count') return p.sp_count || 0;
  if (col === 'labor_total') return p.labor_total || 0;
  return '';
}

function _pfInitSort() {
  const thead = document.querySelector('#portfolioTable thead');
  if (!thead) return;
  thead.querySelectorAll('th[data-sort]').forEach(th => {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    th.addEventListener('click', e => {
      if (e.target.classList.contains('mf-trigger')) return;
      toggleSort(_pfSortState, th.getAttribute('data-sort'));
      renderSortIndicators(thead, _pfSortState);
      renderPortfolio();
    });
  });
  renderSortIndicators(thead, _pfSortState);
}

// ── Фильтрация ──────────────────────────────────────────────────────────
function pfApplyFilters() {
  return portfolioData.filter(p => {
    for (const [col, sel] of Object.entries(pfMfFilters)) {
      if (!sel || sel.size === 0) continue;
      let v = '';
      if (col === 'name') v = p.name_full || p.name_short || '';
      else if (col === 'code') v = p.code || '';
      else if (col === 'status') v = STATUS_LABELS[p.status] || p.status || '';
      else if (col === 'priority_category') v = PRIORITY_LABELS[p.priority_category] || '';
      else if (col === 'chief') v = p.chief_designer ? p.chief_designer.name : '';
      if (!sel.has(v)) return false;
    }
    return true;
  });
}

// ── Загрузка и рендер ───────────────────────────────────────────────────
function loadPortfolio() {
  fetchJSON(`${API}/portfolio/`).then(data => {
    portfolioData = data.projects || [];
    projectsList  = portfolioData;
    renderPortfolio();
    populateProjectSelects();
  }).catch(e => console.error('loadPortfolio:', e));
}

function renderPortfolio() {
  const body = document.getElementById('portfolioBody');
  const empty = document.getElementById('portfolioEmpty');

  let filtered = pfApplyFilters();
  filtered = applySortToArray(filtered, _pfSortState, pfGetSortVal);

  if (!filtered.length) {
    body.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';

  body.innerHTML = filtered.map((p, i) => {
    const chief = p.chief_designer ? escapeHtml(p.chief_designer.name) : '—';
    const prNum = p.priority_number != null ? p.priority_number : '';
    const actions = IS_WRITER
      ? `<button class="btn btn-ghost btn-sm" onclick="openEditProject(${p.id})" title="Редактировать"><i class="fas fa-pen"></i></button>`
      : '';
    return `<tr>
      <td>${i + 1}</td>
      <td>${escapeHtml(p.name_full || p.name_short)}</td>
      <td>${escapeHtml(p.code)}</td>
      <td>${statusBadge(p.status)}</td>
      <td>${prNum ? prNum + '. ' : ''}${priorityBadge(p.priority_category)}</td>
      <td>${chief}</td>
      <td>${p.pp_count}</td>
      <td>${p.sp_count}</td>
      <td>${p.labor_total ? p.labor_total.toLocaleString('ru-RU') : '—'}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('');
}

function openEditProject(id) {
  const p = portfolioData.find(x => x.id === id);
  if (!p) return;
  document.getElementById('editProjectId').value = id;
  document.getElementById('editProjectChief').value = p.chief_designer ? p.chief_designer.id : '';
  document.getElementById('editProjectStatus').value = p.status || 'active';
  document.getElementById('editProjectPriority').value = p.priority_category || '';
  document.getElementById('editProjectPriorityNum').value = p.priority_number || '';
  openModal('projectEditModal');
}

function saveProjectEnterprise() {
  const id = document.getElementById('editProjectId').value;
  const chiefVal = document.getElementById('editProjectChief').value;
  const body = {
    status: document.getElementById('editProjectStatus').value,
    priority_category: document.getElementById('editProjectPriority').value || null,
    priority_number: parseInt(document.getElementById('editProjectPriorityNum').value) || null,
    chief_designer_id: chiefVal ? parseInt(chiefVal) : null,
  };
  fetchJSON(`${API}/portfolio/${id}/`, { method: 'PUT', body: JSON.stringify(body) })
    .then(() => { closeModal('projectEditModal'); loadPortfolio(); })
    .catch(e => alert(e.error || 'Ошибка сохранения'));
}

// ── Создание проекта ─────────────────────────────────────────────────────

function openCreateProject() {
  document.getElementById('createProjectNameFull').value = '';
  document.getElementById('createProjectNameShort').value = '';
  document.getElementById('createProjectCode').value = '';
  document.getElementById('createProjectChief').value = '';
  document.getElementById('createProjectStatus').value = 'active';
  document.getElementById('createProjectPriority').value = '';
  document.getElementById('createProjectPriorityNum').value = '';
  openModal('projectCreateModal');
}

function saveNewProject() {
  const nameFull = document.getElementById('createProjectNameFull').value.trim();
  if (!nameFull) {
    alert('Полное наименование обязательно');
    return;
  }
  const nameShort = document.getElementById('createProjectNameShort').value.trim();
  const code = document.getElementById('createProjectCode').value.trim();

  // 1) Создаём проект через УП API
  fetchJSON('/api/projects/create/', {
    method: 'POST',
    body: JSON.stringify({ name_full: nameFull, name_short: nameShort, code: code }),
  }).then(proj => {
    // 2) Сразу выставляем enterprise-поля (статус, приоритет, ГК)
    const status = document.getElementById('createProjectStatus').value;
    const priority = document.getElementById('createProjectPriority').value || null;
    const priorityNum = parseInt(document.getElementById('createProjectPriorityNum').value) || null;
    const chiefVal = document.getElementById('createProjectChief').value;

    return fetchJSON(`${API}/portfolio/${proj.id}/`, {
      method: 'PUT',
      body: JSON.stringify({
        status: status,
        priority_category: priority,
        priority_number: priorityNum,
        chief_designer_id: chiefVal ? parseInt(chiefVal) : null,
      }),
    });
  }).then(() => {
    closeModal('projectCreateModal');
    loadPortfolio();
  }).catch(e => alert(e.error || 'Ошибка создания проекта'));
}

// Фильтры + сортировка портфеля
function initPortfolioFilters() {
  _pfInitSort();
}

// ══════════════════════════════════════════════════════════════════════════
//  СЕЛЕКТЫ ПРОЕКТОВ (для ГГ и Сквозного графика)
// ══════════════════════════════════════════════════════════════════════════

// ── Project Picker (модалка выбора проекта) ─────────────────────────────

let _pickerTarget = null;  // 'gg' | 'cross' | 'capacity'
let _pickerSortCol = 'priority';
let _pickerSortDir = 'asc';

const PICKER_BTN_MAP = {
  gg:       { btn: 'ggProjectBtn',       input: 'ggProjectSelect',    empty: 'Выберите проект...' },
  cross:    { btn: 'crossProjectBtn',    input: 'crossProjectSelect', empty: 'Выберите проект...' },
  capacity: { btn: 'capacityProjectBtn', input: 'capacityProject',    empty: 'Все проекты' },
};

function openProjectPicker(target) {
  _pickerTarget = target;
  document.getElementById('pickerSearch').value = '';
  renderPickerTable();
  openModal('projectPickerModal');
  setTimeout(() => document.getElementById('pickerSearch').focus(), 100);
}

function closeProjectPicker() {
  closeModal('projectPickerModal');
}

function pickerSort(col) {
  if (_pickerSortCol === col) _pickerSortDir = _pickerSortDir === 'asc' ? 'desc' : 'asc';
  else { _pickerSortCol = col; _pickerSortDir = 'asc'; }
  renderPickerTable();
}

function renderPickerTable() {
  const q = (document.getElementById('pickerSearch').value || '').toLowerCase();
  const curVal = PICKER_BTN_MAP[_pickerTarget] ? document.getElementById(PICKER_BTN_MAP[_pickerTarget].input).value : '';

  let list = portfolioData.filter(p => {
    if (!q) return true;
    const text = ((p.name_short || '') + ' ' + (p.name_full || '') + ' ' + (p.code || '') +
      ' ' + (STATUS_LABELS[p.status] || '') + ' ' + (PRIORITY_LABELS[p.priority_category] || '')).toLowerCase();
    return text.indexOf(q) !== -1;
  });

  // Сортировка
  list.sort((a, b) => {
    let va, vb;
    if (_pickerSortCol === 'num') { va = a.priority_number || 9999; vb = b.priority_number || 9999; }
    else if (_pickerSortCol === 'name') { va = (a.name_short || a.name_full || '').toLowerCase(); vb = (b.name_short || b.name_full || '').toLowerCase(); }
    else if (_pickerSortCol === 'code') { va = (a.code || '').toLowerCase(); vb = (b.code || '').toLowerCase(); }
    else if (_pickerSortCol === 'status') { va = STATUS_LABELS[a.status] || ''; vb = STATUS_LABELS[b.status] || ''; }
    else if (_pickerSortCol === 'priority') { va = PRIORITY_ORDER[a.priority_category] ?? 99; vb = PRIORITY_ORDER[b.priority_category] ?? 99; }
    if (va < vb) return _pickerSortDir === 'asc' ? -1 : 1;
    if (va > vb) return _pickerSortDir === 'asc' ? 1 : -1;
    return 0;
  });

  // Стрелки сортировки
  ['num','name','code','status','priority'].forEach(c => {
    const el = document.getElementById('ps-' + c);
    if (el) el.textContent = _pickerSortCol === c ? (_pickerSortDir === 'asc' ? '▲' : '▼') : '';
  });

  const body = document.getElementById('pickerBody');
  const emptyEl = document.getElementById('pickerEmpty');

  if (!list.length) {
    body.innerHTML = '';
    emptyEl.style.display = '';
  } else {
    emptyEl.style.display = 'none';
    body.innerHTML = list.map((p, i) => {
      const sel = String(p.id) === String(curVal) ? ' picker-selected' : '';
      const name = escapeHtml(p.name_short || p.name_full);
      const code = escapeHtml(p.code || '');
      return `<tr class="${sel}" onclick="selectPickerProject(${p.id})">
        <td>${i + 1}</td>
        <td><strong>${name}</strong></td>
        <td style="color:var(--muted)">${code}</td>
        <td>${statusBadge(p.status)}</td>
        <td>${priorityBadge(p.priority_category)}</td>
      </tr>`;
    }).join('');
  }

  document.getElementById('pickerCount').textContent = 'Найдено: ' + list.length + ' из ' + portfolioData.length;
}

function selectPickerProject(id) {
  const cfg = PICKER_BTN_MAP[_pickerTarget];
  if (!cfg) return;

  const p = portfolioData.find(x => x.id === id);
  const input = document.getElementById(cfg.input);
  const btn = document.getElementById(cfg.btn);

  input.value = id;
  const label = p ? (escapeHtml(p.name_short || p.name_full) + ' (' + escapeHtml(p.code) + ')') : cfg.empty;
  btn.querySelector('.picker-label').innerHTML = label;
  btn.classList.toggle('has-value', !!p);

  closeProjectPicker();

  // Вызываем загрузку данных
  if (_pickerTarget === 'gg') loadGG(id);
  else if (_pickerTarget === 'cross') loadCross(id);
  else if (_pickerTarget === 'capacity') loadCapacity();
}

// Для Загрузки — кнопка «Все проекты» (сброс)
function clearPickerProject(target) {
  const cfg = PICKER_BTN_MAP[target];
  if (!cfg) return;
  document.getElementById(cfg.input).value = '';
  const btn = document.getElementById(cfg.btn);
  btn.querySelector('.picker-label').textContent = cfg.empty;
  btn.classList.remove('has-value');
}

// Привязка поиска
function initPickerSearch() {
  const searchEl = document.getElementById('pickerSearch');
  if (searchEl) searchEl.addEventListener('input', renderPickerTable);
}

function populateProjectSelects() {
  // Больше не нужно заполнять <select> — данные берутся из portfolioData
  // Но обновим кнопки если проект уже выбран (после перезагрузки портфеля)
  Object.entries(PICKER_BTN_MAP).forEach(([target, cfg]) => {
    const input = document.getElementById(cfg.input);
    if (!input || !input.value) return;
    const p = portfolioData.find(x => String(x.id) === String(input.value));
    const btn = document.getElementById(cfg.btn);
    if (p && btn) {
      btn.querySelector('.picker-label').innerHTML = escapeHtml(p.name_short || p.name_full) + ' (' + escapeHtml(p.code) + ')';
      btn.classList.add('has-value');
    }
  });
}

// ══════════════════════════════════════════════════════════════════════════
//  ГЕНЕРАЛЬНЫЙ ГРАФИК
// ══════════════════════════════════════════════════════════════════════════

function initGG() {
  // Выбор проекта теперь через picker-модалку (openProjectPicker → selectPickerProject → loadGG)
}

function loadGG(projectId) {
  fetchJSON(`${API}/gg/${projectId}/`).then(data => {
    currentGG = data.schedule;
    renderGG();
  }).catch(e => console.error('loadGG:', e));
}

function renderGG() {
  const emptyEl   = document.getElementById('ggEmpty');
  const viewEl    = document.getElementById('ggScheduleView');
  const actionsEl = document.getElementById('ggActions');

  if (!currentGG) {
    emptyEl.innerHTML = '<i class="fas fa-stream"></i><p>ГГ не создан. </p>' +
      (IS_WRITER ? '<button class="btn btn-primary btn-sm" onclick="createGG()"><i class="fas fa-plus"></i> Создать ГГ</button>' : '');
    emptyEl.style.display = '';
    viewEl.style.display = 'none';
    actionsEl.innerHTML = '';
    return;
  }

  emptyEl.style.display = 'none';
  viewEl.style.display = '';

  // Кнопки
  actionsEl.innerHTML = IS_WRITER
    ? '<button class="btn btn-primary btn-sm" onclick="addGGStage()"><i class="fas fa-plus"></i> Этап</button>' +
      '<button class="btn btn-outline btn-sm" onclick="addGGMilestone()"><i class="fas fa-flag"></i> Веха</button>'
    : '';

  // Этапы
  const stagesBody = document.getElementById('ggStagesBody');
  stagesBody.innerHTML = (currentGG.stages || []).map(s => {
    const actions = IS_WRITER
      ? `<button class="btn btn-ghost btn-sm" onclick="openEditGGStage(${s.id})" title="Редактировать"><i class="fas fa-pen"></i></button>` +
        `<button class="btn btn-ghost btn-sm" onclick="deleteGGStage(${s.id})" title="Удалить"><i class="fas fa-trash"></i></button>`
      : '';
    return `<tr>
      <td>${s.order}</td>
      <td>${escapeHtml(s.name)}</td>
      <td>${s.date_start || '—'}</td>
      <td>${s.date_end || '—'}</td>
      <td>${s.labor != null ? s.labor : '—'}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="6" class="text-center text-muted">Нет этапов</td></tr>';

  // Вехи
  const msBody = document.getElementById('ggMilestonesBody');
  msBody.innerHTML = (currentGG.milestones || []).map(m => {
    const stageName = currentGG.stages.find(s => s.id === m.stage_id);
    const actions = IS_WRITER
      ? `<button class="btn btn-ghost btn-sm" onclick="deleteGGMilestone(${m.id})" title="Удалить"><i class="fas fa-trash"></i></button>`
      : '';
    return `<tr>
      <td>${escapeHtml(m.name)}</td>
      <td>${m.date || '—'}</td>
      <td>${stageName ? escapeHtml(stageName.name) : '—'}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="4" class="text-center text-muted">Нет вех</td></tr>';
}

function createGG() {
  const pid = document.getElementById('ggProjectSelect').value;
  if (!pid) return;
  fetchJSON(`${API}/gg/${pid}/`, { method: 'POST', body: JSON.stringify({}) })
    .then(() => loadGG(pid))
    .catch(e => alert(e.error || 'Ошибка'));
}

function addGGStage() {
  document.getElementById('ggStageModalTitle').textContent = 'Новый этап';
  document.getElementById('ggStageId').value = '';
  document.getElementById('ggStageName').value = '';
  document.getElementById('ggStageDateStart').value = '';
  document.getElementById('ggStageDateEnd').value = '';
  document.getElementById('ggStageLabor').value = '';
  document.getElementById('ggStageOrder').value = '';
  openModal('ggStageModal');
}

function openEditGGStage(id) {
  const s = (currentGG.stages || []).find(x => x.id === id);
  if (!s) return;
  document.getElementById('ggStageModalTitle').textContent = 'Редактирование этапа';
  document.getElementById('ggStageId').value = id;
  document.getElementById('ggStageName').value = s.name || '';
  document.getElementById('ggStageDateStart').value = s.date_start || '';
  document.getElementById('ggStageDateEnd').value = s.date_end || '';
  document.getElementById('ggStageLabor').value = s.labor != null ? s.labor : '';
  document.getElementById('ggStageOrder').value = s.order != null ? s.order : '';
  openModal('ggStageModal');
}

function saveGGStage() {
  const stageId = document.getElementById('ggStageId').value;
  const name = document.getElementById('ggStageName').value.trim();
  if (!name) { alert('Название обязательно'); return; }
  const body = { name: name };
  const ds = document.getElementById('ggStageDateStart').value;
  const de = document.getElementById('ggStageDateEnd').value;
  const lb = document.getElementById('ggStageLabor').value;
  const ord = document.getElementById('ggStageOrder').value;
  if (ds) body.date_start = ds;
  if (de) body.date_end = de;
  if (lb) body.labor = parseFloat(lb);
  if (ord) body.order = parseInt(ord);

  const pid = document.getElementById('ggProjectSelect').value;
  const url = stageId ? `${API}/gg_stages/${stageId}/` : `${API}/gg/${pid}/stages/`;
  const method = stageId ? 'PUT' : 'POST';

  fetchJSON(url, { method: method, body: JSON.stringify(body) })
    .then(() => { closeModal('ggStageModal'); loadGG(pid); })
    .catch(e => alert(e.error || 'Ошибка сохранения'));
}

function addGGMilestone() {
  const name = prompt('Название вехи:');
  if (!name) return;
  const pid = document.getElementById('ggProjectSelect').value;
  fetchJSON(`${API}/gg/${pid}/milestones/`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  }).then(() => loadGG(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function deleteGGStage(id) {
  if (!confirm('Удалить этап?')) return;
  const pid = document.getElementById('ggProjectSelect').value;
  fetchJSON(`${API}/gg_stages/${id}/`, { method: 'DELETE' })
    .then(() => loadGG(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function deleteGGMilestone(id) {
  if (!confirm('Удалить веху?')) return;
  const pid = document.getElementById('ggProjectSelect').value;
  fetchJSON(`${API}/gg_milestones/${id}/`, { method: 'DELETE' })
    .then(() => loadGG(pid)).catch(e => alert(e.error || 'Ошибка'));
}

// ══════════════════════════════════════════════════════════════════════════
//  СКВОЗНОЙ ГРАФИК
// ══════════════════════════════════════════════════════════════════════════

function initCross() {
  // Выбор проекта теперь через picker-модалку (openProjectPicker → selectPickerProject → loadCross)
}

function loadCross(projectId) {
  fetchJSON(`${API}/cross/${projectId}/`).then(data => {
    currentCross = data.schedule;
    renderCross();
  }).catch(e => console.error('loadCross:', e));
}

const EDIT_OWNER_LABELS = { cross: 'Сквозной', pp: 'ПП', locked: 'Заблокирован' };

function renderCross() {
  const emptyEl   = document.getElementById('crossEmpty');
  const viewEl    = document.getElementById('crossScheduleView');
  const actionsEl = document.getElementById('crossActions');
  const metaEl    = document.getElementById('crossMeta');

  if (!currentCross) {
    emptyEl.innerHTML = '<i class="fas fa-project-diagram"></i><p>Сквозной график не создан.</p>' +
      (IS_WRITER ? '<button class="btn btn-primary btn-sm" onclick="createCross()"><i class="fas fa-plus"></i> Создать</button>' : '');
    emptyEl.style.display = '';
    viewEl.style.display = 'none';
    actionsEl.innerHTML = '';
    return;
  }

  emptyEl.style.display = 'none';
  viewEl.style.display = '';

  // Метабар
  const eo = currentCross.edit_owner;
  metaEl.innerHTML = `
    <div class="ent-meta-item"><span class="ent-meta-label">Версия:</span> ${currentCross.version}</div>
    <div class="ent-meta-item"><span class="ent-meta-label">Режим:</span>
      <span class="edit-lock-badge edit-lock-badge--${eo}">${EDIT_OWNER_LABELS[eo] || escapeHtml(eo)}</span>
    </div>
    <div class="ent-meta-item"><span class="ent-meta-label">Гранулярность:</span> ${currentCross.granularity === 'whole' ? 'Весь график' : 'По отделам'}</div>
  `;

  // Кнопки
  actionsEl.innerHTML = IS_WRITER
    ? '<button class="btn btn-primary btn-sm" onclick="addCrossStage()"><i class="fas fa-plus"></i> Этап</button>' +
      '<button class="btn btn-outline btn-sm" onclick="addCrossMilestone()"><i class="fas fa-flag"></i> Веха</button>' +
      '<button class="btn btn-outline btn-sm" onclick="createBaseline()"><i class="fas fa-camera"></i> Снимок</button>'
    : '';

  // Этапы
  const stagesBody = document.getElementById('crossStagesBody');
  stagesBody.innerHTML = (currentCross.stages || []).map(s => {
    const actions = IS_WRITER && eo !== 'locked'
      ? `<button class="btn btn-ghost btn-sm" onclick="deleteCrossStage(${s.id})" title="Удалить"><i class="fas fa-trash"></i></button>`
      : '';
    return `<tr>
      <td>${s.order}</td>
      <td>${escapeHtml(s.name)}</td>
      <td>${s.department_id || '—'}</td>
      <td>${s.date_start || '—'}</td>
      <td>${s.date_end || '—'}</td>
      <td>${s.gg_stage_id || '—'}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="7" class="text-center text-muted">Нет этапов</td></tr>';

  // Вехи
  const msBody = document.getElementById('crossMilestonesBody');
  msBody.innerHTML = (currentCross.milestones || []).map(m => {
    const stage = (currentCross.stages || []).find(s => s.id === m.cross_stage_id);
    const actions = IS_WRITER && eo !== 'locked'
      ? `<button class="btn btn-ghost btn-sm" onclick="deleteCrossMilestone(${m.id})" title="Удалить"><i class="fas fa-trash"></i></button>`
      : '';
    return `<tr>
      <td>${escapeHtml(m.name)}</td>
      <td>${m.date || '—'}</td>
      <td>${stage ? escapeHtml(stage.name) : '—'}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="4" class="text-center text-muted">Нет вех</td></tr>';
}

function createCross() {
  const pid = document.getElementById('crossProjectSelect').value;
  if (!pid) return;
  fetchJSON(`${API}/cross/${pid}/`, {
    method: 'POST',
    body: JSON.stringify({ from_gg: true }),
  }).then(() => loadCross(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function addCrossStage() {
  const name = prompt('Название этапа:');
  if (!name) return;
  const pid = document.getElementById('crossProjectSelect').value;
  fetchJSON(`${API}/cross/${pid}/stages/`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  }).then(() => loadCross(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function addCrossMilestone() {
  const name = prompt('Название вехи:');
  if (!name) return;
  const pid = document.getElementById('crossProjectSelect').value;
  fetchJSON(`${API}/cross/${pid}/milestones/`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  }).then(() => loadCross(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function deleteCrossStage(id) {
  if (!confirm('Удалить этап?')) return;
  const pid = document.getElementById('crossProjectSelect').value;
  fetchJSON(`${API}/cross_stages/${id}/`, { method: 'DELETE' })
    .then(() => loadCross(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function deleteCrossMilestone(id) {
  if (!confirm('Удалить веху?')) return;
  const pid = document.getElementById('crossProjectSelect').value;
  fetchJSON(`${API}/cross_milestones/${id}/`, { method: 'DELETE' })
    .then(() => loadCross(pid)).catch(e => alert(e.error || 'Ошибка'));
}

function createBaseline() {
  const pid = document.getElementById('crossProjectSelect').value;
  if (!pid) return;
  const comment = prompt('Комментарий к снимку (необязательно):') || '';
  fetchJSON(`${API}/cross/${pid}/baselines/`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  }).then(data => {
    alert(`Снимок v${data.baseline.version} создан`);
    loadCross(pid);
  }).catch(e => alert(e.error || 'Ошибка'));
}

// ══════════════════════════════════════════════════════════════════════════
//  ЗАГРУЗКА / МОЩНОСТЬ
// ══════════════════════════════════════════════════════════════════════════

function initCapacity() {
  document.getElementById('capacityYear').addEventListener('change', loadCapacity);
  document.getElementById('capacityMode').addEventListener('change', loadCapacity);
  // Выбор проекта теперь через picker-модалку
}

function loadCapacity() {
  const year = document.getElementById('capacityYear').value;
  const mode = document.getElementById('capacityMode').value;
  const projectId = document.getElementById('capacityProject').value;

  let url = `${API}/capacity/?year=${year}&mode=${mode}`;
  if (projectId) url += `&project_id=${projectId}`;

  fetchJSON(url).then(data => renderCapacity(data.departments || []))
    .catch(e => console.error('loadCapacity:', e));
}

function renderCapacity(departments) {
  const body = document.getElementById('capacityBody');
  body.innerHTML = departments.map(d => {
    const barWidth = Math.min(d.loading_pct, 150);
    return `<tr>
      <td>${escapeHtml(d.department_name)}</td>
      <td>${d.headcount}</td>
      <td>${d.capacity_hours.toLocaleString('ru-RU')}</td>
      <td>${d.demand_hours.toLocaleString('ru-RU')}</td>
      <td>
        <div class="capacity-cell">
          <div class="loading-bar"><div class="loading-bar-fill loading-bar-fill--${d.level}" style="width:${barWidth}%"></div></div>
          <span class="capacity-pct capacity-pct--${d.level}">${d.loading_pct}%</span>
        </div>
      </td>
      <td>${levelLabel(d.level)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="6" class="text-center text-muted">Нет данных</td></tr>';
}

function levelLabel(level) {
  const m = {
    low:      '<span style="color:#9ca3af">Недозагрузка</span>',
    normal:   '<span style="color:#16a34a">Норма</span>',
    high:     '<span style="color:#ca8a04">Повышенная</span>',
    overload: '<span style="color:#dc2626;font-weight:600">Перегрузка</span>',
  };
  return m[level] || escapeHtml(level);
}

// ══════════════════════════════════════════════════════════════════════════
//  ИНИЦИАЛИЗАЦИЯ
// ══════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initPortfolioFilters();
  initGG();
  initCross();
  initCapacity();
  initPickerSearch();
  populateChiefSelects();
  initHelpPanel();
  loadPortfolio();
});

/* ── Справка-панель: localStorage persistence ──────────────── */
function initHelpPanel() {
  const help = document.getElementById('portfolioHelp');
  if (!help) return;
  if (localStorage.getItem('ent_help_open') === '1') help.open = true;
  help.addEventListener('toggle', () => {
    localStorage.setItem('ent_help_open', help.open ? '1' : '0');
  });
}
