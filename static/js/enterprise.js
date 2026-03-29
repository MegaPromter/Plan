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
      switchToTab(tab.dataset.tab);
    });
  });
}

function switchToTab(target) {
  const tabs = document.querySelectorAll('.ent-tab');
  tabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
  const activeTab = document.querySelector(`.ent-tab[data-tab="${target}"]`);
  if (activeTab) {
    activeTab.classList.add('active');
    activeTab.setAttribute('aria-selected', 'true');
  }

  document.querySelectorAll('.ent-panel').forEach(p => p.style.display = 'none');
  const panel = document.getElementById('panel-' + target);
  if (panel) panel.style.display = '';

  // Загружаем данные при переключении
  if (target === 'capacity') loadCapacity();

  // Сохраняем в hash
  _saveHashState({tab: target});
}

// ── Состояние в URL hash ────────────────────────────────────────────────

function _parseHash() {
  const h = location.hash.replace('#', '');
  const params = {};
  h.split('&').forEach(part => {
    const [k, v] = part.split('=');
    if (k) params[k] = decodeURIComponent(v || '');
  });
  return params;
}

function _saveHashState(updates) {
  const params = _parseHash();
  Object.assign(params, updates);
  const parts = [];
  for (const k in params) {
    if (params[k]) parts.push(k + '=' + encodeURIComponent(params[k]));
  }
  history.replaceState(null, '', '#' + parts.join('&'));
  // Дублируем в localStorage для восстановления при повторном визите
  try { localStorage.setItem('ent_last_state', JSON.stringify(params)); } catch(e) {}
}

function _restoreFromHash() {
  let params = _parseHash();
  // Если hash пуст — восстанавливаем из localStorage
  if (!params.tab && !params.project) {
    try {
      const saved = JSON.parse(localStorage.getItem('ent_last_state') || '{}');
      if (saved.tab) params = saved;
    } catch(e) {}
  }
  const tab = params.tab || 'portfolio';
  switchToTab(tab);

  // Восстанавливаем выбранный проект
  const pid = params.project;
  if (pid) {
    if (tab === 'gg') {
      document.getElementById('ggProjectSelect').value = pid;
      const btn = document.getElementById('ggProjectBtn');
      if (btn) {
        const proj = projectsList.find(p => String(p.id) === String(pid));
        if (proj) btn.textContent = proj.name_short || proj.name_full || proj.code;
      }
      loadGG(pid);
    } else if (tab === 'cross') {
      document.getElementById('crossProjectSelect').value = pid;
      const btn = document.getElementById('crossProjectBtn');
      if (btn) {
        const proj = projectsList.find(p => String(p.id) === String(pid));
        if (proj) btn.textContent = proj.name_short || proj.name_full || proj.code;
      }
      loadCross(pid);
    } else if (tab === 'capacity') {
      document.getElementById('capacityProjectSelect').value = pid;
      const btn = document.getElementById('capacityProjectBtn');
      if (btn) {
        const proj = projectsList.find(p => String(p.id) === String(pid));
        if (proj) btn.textContent = proj.name_short || proj.name_full || proj.code;
      }
      loadCapacity();
    }
  }
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
    // Восстанавливаем вкладку и проект из URL hash
    if (!loadPortfolio._restored) {
      loadPortfolio._restored = true;
      _restoreFromHash();
    }
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

  // Сохраняем в hash и загружаем данные
  _saveHashState({project: id});
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
    ? '<button class="btn btn-primary btn-sm" onclick="addGGStage()"><i class="fas fa-plus"></i> Пункт</button>' +
      '<button class="btn btn-outline btn-sm" onclick="addGGMilestone()"><i class="fas fa-flag"></i> Веха</button>'
    : '';

  // Пункты
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
  }).join('') || '<tr><td colspan="6" class="text-center text-muted">Нет пунктов</td></tr>';

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

  // Если активен вид Ганта — обновляем диаграмму
  if (ggCurrentView === 'gantt' && ggGanttLoaded) {
    renderGGGantt();
  }
}

function createGG() {
  const pid = document.getElementById('ggProjectSelect').value;
  if (!pid) return;
  fetchJSON(`${API}/gg/${pid}/`, { method: 'POST', body: JSON.stringify({}) })
    .then(() => loadGG(pid))
    .catch(e => alert(e.error || 'Ошибка'));
}

function addGGStage() {
  document.getElementById('ggStageModalTitle').textContent = 'Новый пункт';
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
  document.getElementById('ggStageModalTitle').textContent = 'Редактирование пункта';
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
  if (!confirm('Удалить пункт?')) return;
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

// ── Переключатель Таблица / Гант ──────────────────────────────────────────

let ggGanttLoaded = false;   // библиотека загружена
let ggGanttInited = false;   // gantt.init() вызван
let ggCurrentView = 'table'; // table | gantt

function switchGGView(view) {
  ggCurrentView = view;
  const tableEl = document.getElementById('ggTableView');
  const ganttEl = document.getElementById('ggGanttContainer');
  const scalesEl = document.getElementById('ggGanttScales');
  const btnTable = document.getElementById('ggViewTable');
  const btnGantt = document.getElementById('ggViewGantt');

  if (view === 'gantt') {
    tableEl.style.display = 'none';
    ganttEl.style.display = '';
    scalesEl.style.display = '';
    btnTable.classList.remove('active');
    btnGantt.classList.add('active');
    if (!ggGanttLoaded) {
      loadGGGantt();
    } else {
      renderGGGantt();
    }
  } else {
    tableEl.style.display = '';
    ganttEl.style.display = 'none';
    scalesEl.style.display = 'none';
    btnTable.classList.add('active');
    btnGantt.classList.remove('active');
  }
}

// ── Lazy-load dhtmlxGantt ─────────────────────────────────────────────────

function loadGGGantt() {
  ganttLoad(() => {
    ggGanttLoaded = true;
    setupGGGantt();
    renderGGGantt();
  }, 'ggGanttContainer');
}

// ── Настройка Ганта ───────────────────────────────────────────────────────

const _GG_COL_KEY = 'gg_gantt_col_widths';
const _GG_COL_DEFAULTS = { text: 200, start_date: 70, end_date: 70, grid: 340 };

function setupGGGantt() {
  if (typeof gantt === 'undefined' || ggGanttInited) return;
  ggGanttInited = true;

  ganttSetupBase();

  // Колонки с восстановлением ширин
  const savedCols = ganttLoadColWidths(_GG_COL_KEY, _GG_COL_DEFAULTS);
  gantt.config.grid_width = savedCols.grid;
  gantt.config.columns = [
    { name: "text", label: "Название", width: savedCols.text, tree: true, resize: true },
    { name: "start_date", label: "Начало", align: "center", width: savedCols.start_date, resize: true },
    { name: "end_date", label: "Окончание", align: "center", width: savedCols.end_date, resize: true },
  ];

  // Интерактивный режим для writers
  gantt.config.readonly = !IS_WRITER;
  gantt.config.drag_move = IS_WRITER;
  gantt.config.drag_resize = IS_WRITER;
  gantt.config.drag_progress = false;
  gantt.config.drag_links = false;
  gantt.config.show_links = true;

  ganttRestoreScale('gg_gantt_scale');
  gantt.init("ggGanttContainer");

  // Resize колонок
  gantt.attachEvent("onGanttRender", () => ganttInjectResizers('ggGanttContainer', _GG_COL_KEY));

  // Drag → сохранение дат на сервере
  gantt.attachEvent("onAfterTaskDrag", function(id) {
    const task = gantt.getTask(id);
    if (!task || !task.server_id) return;
    const startStr = ganttFormatDate(task.start_date);
    const endStr = ganttFormatDate(task.end_date);
    const isMilestone = task.type === gantt.config.types.milestone;
    const url = isMilestone
      ? `${API}/gg_milestones/${task.server_id}/`
      : `${API}/gg_stages/${task.server_id}/`;
    const body = isMilestone ? { date: startStr } : { date_start: startStr, date_end: endStr };
    fetchJSON(url, { method: 'PUT', body: JSON.stringify(body) })
      .then(() => {
        if (isMilestone) {
          const m = (currentGG.milestones || []).find(x => x.id === task.server_id);
          if (m) m.date = startStr;
        } else {
          const s = (currentGG.stages || []).find(x => x.id === task.server_id);
          if (s) { s.date_start = startStr; s.date_end = endStr; }
        }
      })
      .catch(e => { alert(e.error || 'Ошибка сохранения'); renderGGGantt(); });
  });

  // Двойной клик → модалка редактирования
  gantt.attachEvent("onBeforeLightbox", function(id) {
    const task = gantt.getTask(id);
    if (task && task.server_id && task.type !== gantt.config.types.milestone) {
      openEditGGStage(task.server_id);
    }
    return false;
  });
}

// ── Масштаб Ганта ─────────────────────────────────────────────────────────

function setGGGanttScale(scale) {
  ganttSetScale(scale, 'gg_gantt_scale', '#ggGanttScales');
}

// ── Отрисовка данных в Ганте ──────────────────────────────────────────────

function renderGGGantt() {
  if (typeof gantt === 'undefined' || !currentGG) return;

  const tasks = [];
  const links = [];

  // Пункты (stages) → задачи Ганта
  (currentGG.stages || []).forEach(s => {
    if (!s.date_start || !s.date_end) return; // пропускаем без дат
    const isParent = (currentGG.stages || []).some(c => c.parent_stage_id === s.id);
    tasks.push({
      id: 'stage_' + s.id,
      server_id: s.id,
      text: s.name,
      start_date: s.date_start,
      end_date: s.date_end,
      parent: s.parent_stage_id ? 'stage_' + s.parent_stage_id : 0,
      type: isParent ? gantt.config.types.project : gantt.config.types.task,
      open: true,
    });
  });

  // Вехи → milestone-тип
  (currentGG.milestones || []).forEach(m => {
    if (!m.date) return;
    tasks.push({
      id: 'ms_' + m.id,
      server_id: m.id,
      text: m.name,
      start_date: m.date,
      duration: 0,
      parent: m.stage_id ? 'stage_' + m.stage_id : 0,
      type: gantt.config.types.milestone,
    });
  });

  // Зависимости → links
  const depTypeMap = { FS: '0', SS: '1', FF: '2', SF: '3' };
  (currentGG.dependencies || []).forEach(d => {
    links.push({
      id: 'dep_' + d.id,
      source: 'stage_' + d.predecessor_id,
      target: 'stage_' + d.successor_id,
      type: depTypeMap[d.dep_type] || '0',
      lag: d.lag_days || 0,
    });
  });

  gantt.clearAll();
  gantt.parse({ data: tasks, links: links });

  // Авто-высота строк + масштаб
  ganttAutoFitRowHeights();
  setGGGanttScale(localStorage.getItem('gg_gantt_scale') || 'year');
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
    // Заголовок с названием проекта
    const proj = portfolioData.find(p => p.id === +projectId);
    const titleEl = document.getElementById('crossTitle');
    if (titleEl) {
      titleEl.textContent = proj
        ? 'Сквозной график по проекту ' + (proj.name_short || proj.name_full)
        : 'Сквозной график';
    }
    renderCross();
  }).catch(e => console.error('loadCross:', e));
}

const EDIT_OWNER_LABELS = { cross: 'Сквозной', pp: 'ПП', locked: 'Заблокирован' };

function onCrossSettingChange() {
  const modeEl = document.getElementById('crossModeSelect');
  const granEl = document.getElementById('crossGranSelect');
  const btn = document.getElementById('crossSettingsApply');
  if (!modeEl || !granEl || !btn) return;

  const changed = modeEl.value !== currentCross.edit_owner || granEl.value !== currentCross.granularity;
  btn.style.display = changed ? '' : 'none';

  // Обновляем цвет селекта режима
  modeEl.className = 'edit-owner-select edit-owner-select--' + modeEl.value;
}

function applyCrossSettings() {
  const pid = selectedProjectId;
  if (!pid) return;

  const modeEl = document.getElementById('crossModeSelect');
  const granEl = document.getElementById('crossGranSelect');
  const body = {};
  if (modeEl.value !== currentCross.edit_owner) body.edit_owner = modeEl.value;
  if (granEl.value !== currentCross.granularity) body.granularity = granEl.value;
  if (!Object.keys(body).length) return;

  const LABELS = { cross: 'Сквозной', pp: 'ПП', locked: 'Заблокирован' };
  if (body.edit_owner === 'locked') {
    if (!confirm('Заблокировать график? Редактирование станет невозможным.')) {
      modeEl.value = currentCross.edit_owner;
      onCrossSettingChange();
      return;
    }
  }

  fetchJSON(`${API}/cross/${pid}/`, {
    method: 'PUT',
    body: JSON.stringify(body),
  }).then(() => {
    if (body.edit_owner) currentCross.edit_owner = body.edit_owner;
    if (body.granularity) currentCross.granularity = body.granularity;
    renderCross();
    showToast('Настройки сохранены', 'success');
  }).catch(e => alert(e.error || 'Ошибка'));
}

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
  const modeSelector = IS_WRITER
    ? `<select id="crossModeSelect" class="edit-owner-select edit-owner-select--${eo}" onchange="onCrossSettingChange()">
         <option value="cross"${eo === 'cross' ? ' selected' : ''}>Сквозной</option>
         <option value="pp"${eo === 'pp' ? ' selected' : ''}>ПП</option>
         <option value="locked"${eo === 'locked' ? ' selected' : ''}>Заблокирован</option>
       </select>`
    : `<span class="edit-lock-badge edit-lock-badge--${eo}">${EDIT_OWNER_LABELS[eo] || escapeHtml(eo)}</span>`;

  const gran = currentCross.granularity;
  const granSelector = IS_WRITER
    ? `<select id="crossGranSelect" class="edit-owner-select" onchange="onCrossSettingChange()">
         <option value="whole"${gran === 'whole' ? ' selected' : ''}>Весь график</option>
         <option value="per_dept"${gran === 'per_dept' ? ' selected' : ''}>По отделам</option>
       </select>`
    : (gran === 'whole' ? 'Весь график' : 'По отделам');

  metaEl.innerHTML = `
    <div class="ent-meta-item"><span class="ent-meta-label">Версия:</span>
      <a href="#" class="baseline-version-link" onclick="openBaselineList(); return false;">${currentCross.version}</a>
    </div>
    <div class="ent-meta-item"><span class="ent-meta-label">Режим:</span> ${modeSelector}</div>
    <div class="ent-meta-item"><span class="ent-meta-label">Гранулярность:</span> ${granSelector}</div>
    ${IS_WRITER ? '<button id="crossSettingsApply" class="btn btn-primary btn-sm" style="display:none;" onclick="applyCrossSettings()"><i class="fas fa-check"></i> Применить</button>' : ''}
  `;

  // Кнопки
  actionsEl.innerHTML = IS_WRITER && eo !== 'locked'
    ? '<button class="btn btn-primary btn-sm" onclick="addCrossStage()"><i class="fas fa-plus"></i> Этап</button>' +
      '<button class="btn btn-outline btn-sm" onclick="addCrossMilestone()"><i class="fas fa-flag"></i> Веха</button>' +
      '<button class="btn btn-outline btn-sm" onclick="createBaseline()"><i class="fas fa-camera"></i> Снимок</button>'
    : '';

  // Пункты (из ГГ) + этапы (вложенные) + работы
  const canAssign = IS_WRITER && eo === 'cross';
  const stages = currentCross.stages || [];

  // Пункты: is_item=true (parent_item_id === null)
  // Этапы: is_item=false (parent_item_id !== null)
  const ggItems = stages.filter(s => s.is_item);
  const subStages = stages.filter(s => !s.is_item);
  const subByParent = {};
  subStages.forEach(s => {
    const pid = s.parent_item_id;
    if (!subByParent[pid]) subByParent[pid] = [];
    subByParent[pid].push(s);
  });

  const tableBody = document.getElementById('crossTableBody');
  let rowsHtml = '';

  // Вспомогательная: строки работ для этапа
  function _workRows(stageId, works) {
    return works.map(w => {
      const unlink = canAssign
        ? `<button class="btn btn-ghost btn-sm btn-danger-text" onclick="unlinkWork(${stageId}, ${w.id})" title="Отвязать"><i class="fas fa-unlink"></i></button>`
        : '';
      return `<tr class="cross-lv2" data-stage="${stageId}" style="display:none;">
        <td>${escapeHtml(w.name)}</td>
        <td>${w.date_start || '—'}</td>
        <td>${w.date_end || '—'}</td>
        <td>${w.labor != null ? w.labor : '—'}</td>
        <td>${escapeHtml(w.department)}</td>
        <td>${unlink}</td>
      </tr>`;
    }).join('');
  }

  ggItems.forEach(item => {
    const itemNum = item.order;
    const totalWorks = (item.works_count || 0) + (subByParent[item.id] || []).reduce((s, sub) => s + (sub.works_count || 0), 0);
    const assignBtn = canAssign
      ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openAssignWorks(${item.id})" title="Привязать работы"><i class="fas fa-link"></i></button>`
      : '';

    // Пункт ГГ — lv0
    rowsHtml += `<tr class="cross-lv0">
      <td>${itemNum}. ${escapeHtml(item.name)} ${totalWorks > 0 ? `<span class="cross-works-badge">${totalWorks}</span>` : ''}</td>
      <td>${item.date_start || '—'}</td>
      <td>${item.date_end || '—'}</td>
      <td></td><td></td>
      <td>${assignBtn}</td>
    </tr>`;

    // Работы пункта напрямую
    if ((item.works_count || 0) > 0) rowsHtml += _workRows(item.id, item.works);

    // Вложенные этапы
    const subs = subByParent[item.id] || [];
    subs.forEach((sub, idx) => {
      const subNum = itemNum + '.' + (idx + 1);
      const swc = sub.works_count || 0;
      const sBadge = swc > 0 ? `<span class="cross-works-badge">${swc}</span>` : '';
      const sToggleClick = swc > 0 ? `onclick="toggleCrossStageWorks(${sub.id})" style="cursor:pointer;"` : '';
      const sChevron = swc > 0 ? '<i class="fas fa-chevron-right cross-chevron"></i> ' : '';
      const sAssignBtn = canAssign
        ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openAssignWorks(${sub.id})" title="Привязать работы"><i class="fas fa-link"></i></button>`
        : '';
      const editBtn = IS_WRITER && eo !== 'locked'
        ? `<button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openEditCrossStage(${sub.id})" title="Редактировать"><i class="fas fa-pen"></i></button>`
        : '';

      rowsHtml += `<tr class="cross-lv1" ${sToggleClick}>
        <td>${sChevron}${subNum}. ${escapeHtml(sub.name)} ${sBadge}</td>
        <td>${sub.date_start || '—'}</td>
        <td>${sub.date_end || '—'}</td>
        <td></td><td></td>
        <td>${editBtn}${sAssignBtn}</td>
      </tr>`;

      if (swc > 0) rowsHtml += _workRows(sub.id, sub.works);
    });
  });

  tableBody.innerHTML = rowsHtml || '<tr><td colspan="6" class="text-center text-muted">Нет пунктов</td></tr>';

  // Неназначенные работы ПП
  const unassigned = currentCross.unassigned_works || [];
  let unassignedEl = document.getElementById('crossUnassignedSection');
  if (unassigned.length > 0) {
    if (!unassignedEl) {
      unassignedEl = document.createElement('div');
      unassignedEl.id = 'crossUnassignedSection';
      document.getElementById('crossStagesSection').after(unassignedEl);
    }
    unassignedEl.innerHTML = `
      <div class="ent-section">
        <div class="ent-section-title">Неназначенные работы ПП <span class="cross-works-badge">${unassigned.length}</span></div>
        <table class="cross-table">
          <thead><tr><th>Название</th><th style="width:110px;">Начало</th><th style="width:110px;">Окончание</th><th style="width:80px;">Труд.</th><th style="width:100px;">Отдел</th><th style="width:60px;"></th></tr></thead>
          <tbody>${unassigned.map(w => `<tr class="cross-lv2">
            <td>${escapeHtml(w.name)}</td>
            <td>${w.date_start || '—'}</td>
            <td>${w.date_end || '—'}</td>
            <td>${w.labor != null ? w.labor : '—'}</td>
            <td>${escapeHtml(w.department)}</td>
            <td></td>
          </tr>`).join('')}</tbody>
        </table>
      </div>`;
  } else if (unassignedEl) {
    unassignedEl.innerHTML = '';
  }

  // Вехи
  const msBody = document.getElementById('crossMilestonesBody');
  msBody.innerHTML = (currentCross.milestones || []).map(m => {
    const linked = (currentCross.stages || []).find(s => s.id === m.cross_stage_id);
    // Для вехи показываем пункт: если linked — gg_stage_id, ищем пункт
    let itemName = '—';
    if (linked) {
      const parent = linked.gg_stage_id
        ? ggItems.find(g => g.id === linked.gg_stage_id)
        : linked;
      itemName = parent ? escapeHtml(parent.name) : escapeHtml(linked.name);
    }
    const actions = IS_WRITER && eo !== 'locked'
      ? `<button class="btn btn-ghost btn-sm" onclick="deleteCrossMilestone(${m.id})" title="Удалить"><i class="fas fa-trash"></i></button>`
      : '';
    return `<tr>
      <td>${escapeHtml(m.name)}</td>
      <td>${m.date || '—'}</td>
      <td>${itemName}</td>
      <td>${actions}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="4" class="text-center text-muted">Нет вех</td></tr>';
}

// ── Работы в этапах сквозного графика ────────────────────────────────────

function toggleCrossStageWorks(stageId) {
  const workRows = document.querySelectorAll(`tr.cross-lv2[data-stage="${stageId}"]`);
  if (!workRows.length) return;
  const visible = workRows[0].style.display !== 'none';
  workRows.forEach(r => r.style.display = visible ? 'none' : '');

  const first = workRows[0];
  const parentRow = first.previousElementSibling;
  const chevron = parentRow && parentRow.querySelector('.cross-chevron');
  if (chevron) {
    chevron.classList.toggle('fa-chevron-right', visible);
    chevron.classList.toggle('fa-chevron-down', !visible);
  }
}

function crossExpandAll() {
  document.querySelectorAll('.cross-lv2').forEach(r => r.style.display = '');
  document.querySelectorAll('.cross-chevron').forEach(ch => {
    ch.classList.remove('fa-chevron-right');
    ch.classList.add('fa-chevron-down');
  });
}

function crossCollapseAll() {
  document.querySelectorAll('.cross-lv2').forEach(r => r.style.display = 'none');
  document.querySelectorAll('.cross-chevron').forEach(ch => {
    ch.classList.remove('fa-chevron-down');
    ch.classList.add('fa-chevron-right');
  });
}

function openAssignWorks(stageId) {
  const unassigned = currentCross.unassigned_works || [];
  if (!unassigned.length) {
    showToast('Нет неназначенных работ ПП', 'info');
    return;
  }

  let modal = document.getElementById('assignWorksModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'assignWorksModal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
    let _bDown = null;
    modal.addEventListener('mousedown', e => { _bDown = e.target; });
    modal.addEventListener('click', e => {
      if (e.target === modal && _bDown === modal) modal.classList.remove('open');
    });
  }

  const stage = (currentCross.stages || []).find(s => s.id === stageId);
  const stageName = stage ? escapeHtml(stage.name) : stageId;

  const rows = unassigned.map(w => `<tr>
    <td><input type="checkbox" class="assign-work-cb" data-id="${w.id}"></td>
    <td class="text-muted">${escapeHtml(w.row_code)}</td>
    <td>${escapeHtml(w.name)}</td>
    <td>${w.date_start || '—'}</td>
    <td>${w.date_end || '—'}</td>
    <td>${w.labor != null ? w.labor : '—'}</td>
    <td>${escapeHtml(w.executor)}</td>
  </tr>`).join('');

  modal.innerHTML = `
    <div class="modal" style="max-width:800px;">
      <div class="modal-header">
        <h3>Привязать работы к этапу «${stageName}»</h3>
        <button class="modal-close" onclick="document.getElementById('assignWorksModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body" style="overflow-x:auto;">
        <table class="cross-works-table">
          <thead><tr>
            <th style="width:32px;"><input type="checkbox" onchange="document.querySelectorAll('.assign-work-cb').forEach(c=>c.checked=this.checked)"></th>
            <th>Код</th><th>Работа</th><th>Начало</th><th>Окончание</th><th>Труд.</th><th>Исполнитель</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div style="margin-top:12px;display:flex;gap:8px;">
          <button class="btn btn-primary btn-sm" onclick="doAssignWorks(${stageId})"><i class="fas fa-link"></i> Привязать выбранные</button>
          <button class="btn btn-outline btn-sm" onclick="document.getElementById('assignWorksModal').classList.remove('open')">Отмена</button>
        </div>
      </div>
    </div>
  `;
  modal.classList.add('open');
}

function doAssignWorks(stageId) {
  const cbs = document.querySelectorAll('.assign-work-cb:checked');
  const ids = [...cbs].map(c => +c.dataset.id);
  if (!ids.length) { showToast('Выберите работы', 'warning'); return; }

  fetchJSON(`${API}/cross_stages/${stageId}/works/`, {
    method: 'POST',
    body: JSON.stringify({ work_ids: ids }),
  }).then(() => {
    document.getElementById('assignWorksModal').classList.remove('open');
    showToast(`Привязано работ: ${ids.length}`, 'success');
    loadCross(selectedProjectId);
  }).catch(e => alert(e.error || 'Ошибка'));
}

function unlinkWork(stageId, workId) {
  if (!confirm('Отвязать работу от этапа?')) return;
  fetchJSON(`${API}/cross_stages/${stageId}/works/`, {
    method: 'DELETE',
    body: JSON.stringify({ work_ids: [workId] }),
  }).then(() => {
    showToast('Работа отвязана', 'success');
    loadCross(selectedProjectId);
  }).catch(e => alert(e.error || 'Ошибка'));
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
  document.getElementById('crossStageModalTitle').textContent = 'Новый этап';
  document.getElementById('crossStageId').value = '';
  document.getElementById('crossStageName').value = '';
  document.getElementById('crossStageDateStart').value = '';
  document.getElementById('crossStageDateEnd').value = '';

  // Заполнить дропдаун пунктами (is_item = true)
  const sel = document.getElementById('crossStageGGItem');
  const items = (currentCross.stages || []).filter(s => s.is_item);
  sel.innerHTML = '<option value="">— Выберите пункт —</option>' +
    items.map(s => `<option value="${s.id}">${s.order}. ${escapeHtml(s.name)}</option>`).join('');

  openModal('crossStageModal');
}

function openEditCrossStage(id) {
  const s = (currentCross.stages || []).find(x => x.id === id);
  if (!s) return;
  document.getElementById('crossStageModalTitle').textContent = 'Редактирование этапа';
  document.getElementById('crossStageId').value = id;
  document.getElementById('crossStageName').value = s.name || '';
  document.getElementById('crossStageDateStart').value = s.date_start || '';
  document.getElementById('crossStageDateEnd').value = s.date_end || '';

  const sel = document.getElementById('crossStageGGItem');
  const items = (currentCross.stages || []).filter(x => x.is_item);
  sel.innerHTML = '<option value="">— Выберите пункт —</option>' +
    items.map(x => `<option value="${x.id}"${x.id === s.parent_item_id ? ' selected' : ''}>${x.order}. ${escapeHtml(x.name)}</option>`).join('');

  openModal('crossStageModal');
}

function saveCrossStage() {
  const stageId = document.getElementById('crossStageId').value;
  const name = document.getElementById('crossStageName').value.trim();
  if (!name) { alert('Название обязательно'); return; }

  const parentItemId = document.getElementById('crossStageGGItem').value;
  if (!parentItemId) { alert('Выберите пункт'); return; }

  const body = { name, parent_item_id: +parentItemId };
  const ds = document.getElementById('crossStageDateStart').value;
  const de = document.getElementById('crossStageDateEnd').value;
  if (ds) body.date_start = ds;
  if (de) body.date_end = de;

  const pid = document.getElementById('crossProjectSelect').value;
  const url = stageId ? `${API}/cross_stages/${stageId}/` : `${API}/cross/${pid}/stages/`;
  const method = stageId ? 'PUT' : 'POST';

  fetchJSON(url, { method, body: JSON.stringify(body) })
    .then(() => { closeModal('crossStageModal'); loadCross(pid); })
    .catch(e => alert(e.error || 'Ошибка сохранения'));
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

  let modal = document.getElementById('baselineCreateModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'baselineCreateModal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
    let _down = null;
    modal.addEventListener('mousedown', e => { _down = e.target; });
    modal.addEventListener('click', e => {
      if (e.target === modal && _down === modal) modal.classList.remove('open');
    });
  }

  modal.innerHTML = `
    <div class="modal" style="max-width:460px;">
      <div class="modal-header">
        <h3>Создать снимок</h3>
        <button class="modal-close" onclick="document.getElementById('baselineCreateModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body">
        <label style="display:block; font-size:13px; font-weight:500; margin-bottom:6px;">Комментарий (необязательно)</label>
        <textarea id="baselineComment" rows="3" style="width:100%; resize:vertical; padding:8px 10px; border:1px solid var(--border); border-radius:8px; font-size:13px; font-family:inherit;" placeholder="Опишите причину или содержание снимка..."></textarea>
      </div>
      <div class="modal-footer" style="display:flex; justify-content:flex-end; gap:8px;">
        <button class="btn btn-outline btn-sm" onclick="document.getElementById('baselineCreateModal').classList.remove('open')">Отмена</button>
        <button class="btn btn-primary btn-sm" id="baselineCreateBtn"><i class="fas fa-camera"></i> Создать</button>
      </div>
    </div>
  `;
  modal.classList.add('open');
  modal.querySelector('#baselineComment').focus();

  modal.querySelector('#baselineCreateBtn').addEventListener('click', () => {
    const comment = modal.querySelector('#baselineComment').value.trim();
    const btn = modal.querySelector('#baselineCreateBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Создание...';

    fetchJSON(`${API}/cross/${pid}/baselines/`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }).then(data => {
      modal.classList.remove('open');
      showToast(`Снимок v${data.baseline.version} создан`, 'success');
      loadCross(pid);
    }).catch(e => {
      btn.disabled = false;
      btn.innerHTML = '<i class="fas fa-camera"></i> Создать';
      alert(e.error || 'Ошибка');
    });
  });
}

// ── Список снимков (baseline) ───────────────────────────────────────────

let baselinesCache = [];

function openBaselineList() {
  const pid = document.getElementById('crossProjectSelect').value;
  if (!pid) return;

  fetchJSON(`${API}/cross/${pid}/baselines/`).then(data => {
    baselinesCache = data.baselines || [];
    renderBaselineModal();
  }).catch(e => alert(e.error || 'Ошибка'));
}

function renderBaselineModal() {
  let modal = document.getElementById('baselineModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'baselineModal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
    // Закрытие по клику на overlay
    let _bDown = null;
    modal.addEventListener('mousedown', e => { _bDown = e.target; });
    modal.addEventListener('click', e => {
      if (e.target === modal && _bDown === modal) modal.classList.remove('open');
    });
  }

  const rows = baselinesCache.length
    ? baselinesCache.map(b => {
        const date = new Date(b.created_at).toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});
        return `<tr>
          <td><label class="baseline-check"><input type="checkbox" class="bl-compare-cb" data-id="${b.id}" data-version="${b.version}" onchange="onBaselineCheckChange()"><span></span></label></td>
          <td><strong>v${b.version}</strong></td>
          <td>${date}</td>
          <td>${escapeHtml(b.created_by || '—')}</td>
          <td>${escapeHtml(b.comment || '—')}</td>
          <td>
            <button class="btn btn-ghost btn-sm" onclick="viewBaseline(${b.id})" title="Просмотр"><i class="fas fa-eye"></i></button>
            <button class="btn btn-ghost btn-sm" onclick="compareBaselineWithCurrent(${b.id}, ${b.version})" title="Сравнить с текущим"><i class="fas fa-not-equal"></i></button>
            ${IS_WRITER ? `<button class="btn btn-ghost btn-sm btn-danger-text" onclick="deleteBaseline(${b.id})" title="Удалить"><i class="fas fa-trash"></i></button>` : ''}
          </td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="6" class="text-center text-muted">Нет снимков</td></tr>';

  const compareBtn = baselinesCache.length >= 2
    ? `<button id="blCompareBtn" class="btn btn-outline btn-sm" onclick="compareTwoBaselines()" disabled>
         <i class="fas fa-columns"></i> Сравнить выбранные
       </button>`
    : '';

  modal.innerHTML = `
    <div class="modal" style="max-width:780px;">
      <div class="modal-header">
        <h3>Снимки (Baselines)</h3>
        <button class="modal-close" onclick="document.getElementById('baselineModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body" style="overflow-x:auto;">
        ${compareBtn ? `<div style="margin-bottom:10px;">${compareBtn} <span id="blCompareHint" class="text-muted" style="font-size:12px;margin-left:8px;">Выберите 2 снимка для сравнения</span></div>` : ''}
        <table class="baseline-table">
          <thead><tr>
            <th style="width:32px;"></th>
            <th>Версия</th><th>Дата</th><th>Автор</th><th>Комментарий</th><th>Действия</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
  `;
  modal.classList.add('open');
}

// ── Просмотр снимка ─────────────────────────────────────────────────────

function viewBaseline(id) {
  fetchJSON(`${API}/baselines/${id}/`).then(data => {
    const b = data.baseline;
    renderBaselineView(b);
  }).catch(e => alert(e.error || 'Ошибка'));
}

function renderBaselineView(b) {
  // Ищем запись со state этапов/вех
  const stateEntry = (b.entries || []).find(e => e.data && e.data._type === 'schedule_state');
  const stages = stateEntry ? (stateEntry.data.stages || []) : [];
  const milestones = stateEntry ? (stateEntry.data.milestones || []) : [];

  const date = new Date(b.created_at).toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});

  const stageRows = stages.length
    ? stages.map(s => `<tr>
        <td>${s.order}</td>
        <td>${escapeHtml(s.name)}</td>
        <td>${s.date_start || '—'}</td>
        <td>${s.date_end || '—'}</td>
      </tr>`).join('')
    : '<tr><td colspan="4" class="text-center text-muted">Нет этапов</td></tr>';

  const msRows = milestones.length
    ? milestones.map(m => {
        const stage = stages.find(s => s.id === m.cross_stage_id);
        return `<tr>
          <td>${escapeHtml(m.name)}</td>
          <td>${m.date || '—'}</td>
          <td>${stage ? escapeHtml(stage.name) : '—'}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="3" class="text-center text-muted">Нет вех</td></tr>';

  let modal = document.getElementById('baselineModal');
  modal.innerHTML = `
    <div class="modal" style="max-width:800px;">
      <div class="modal-header">
        <h3>Снимок v${b.version}</h3>
        <button class="modal-close" onclick="document.getElementById('baselineModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="baseline-view-meta">
          <span><strong>Дата:</strong> ${date}</span>
          <span><strong>Автор:</strong> ${escapeHtml(b.created_by || '—')}</span>
          <span><strong>Комментарий:</strong> ${escapeHtml(b.comment || '—')}</span>
        </div>
        <h4 style="margin:16px 0 8px;">Этапы</h4>
        <table class="baseline-table">
          <thead><tr><th>№</th><th>Название</th><th>Начало</th><th>Окончание</th></tr></thead>
          <tbody>${stageRows}</tbody>
        </table>
        <h4 style="margin:16px 0 8px;">Вехи</h4>
        <table class="baseline-table">
          <thead><tr><th>Название</th><th>Дата</th><th>Этап</th></tr></thead>
          <tbody>${msRows}</tbody>
        </table>
        <div style="margin-top:16px;">
          <button class="btn btn-outline btn-sm" onclick="openBaselineList()"><i class="fas fa-arrow-left"></i> Назад к списку</button>
        </div>
      </div>
    </div>
  `;
}

// ── Выбор снимков для сравнения ──────────────────────────────────────────

function onBaselineCheckChange() {
  const cbs = document.querySelectorAll('.bl-compare-cb:checked');
  const btn = document.getElementById('blCompareBtn');
  const hint = document.getElementById('blCompareHint');
  if (!btn) return;

  if (cbs.length > 2) {
    // Снимаем первый из отмеченных (FIFO)
    cbs[0].checked = false;
  }
  const checked = document.querySelectorAll('.bl-compare-cb:checked');
  btn.disabled = checked.length !== 2;
  if (hint) {
    hint.textContent = checked.length === 2
      ? `v${checked[0].dataset.version} ↔ v${checked[1].dataset.version}`
      : 'Выберите 2 снимка для сравнения';
  }
}

function compareTwoBaselines() {
  const cbs = [...document.querySelectorAll('.bl-compare-cb:checked')];
  if (cbs.length !== 2) return;

  // Сортируем: меньшая версия = left (старая), большая = right (новая)
  cbs.sort((a, b) => +a.dataset.version - +b.dataset.version);
  const idA = +cbs[0].dataset.id;
  const idB = +cbs[1].dataset.id;

  Promise.all([
    fetchJSON(`${API}/baselines/${idA}/`),
    fetchJSON(`${API}/baselines/${idB}/`),
  ]).then(([dataA, dataB]) => {
    renderBaselineComparison(dataA.baseline, dataB.baseline);
  }).catch(e => alert(e.error || 'Ошибка'));
}

// ── Сравнение снимка с текущим ──────────────────────────────────────────

function compareBaselineWithCurrent(id, version) {
  if (!currentCross) return;

  fetchJSON(`${API}/baselines/${id}/`).then(data => {
    // Создаём «виртуальный» правый снимок из текущего состояния
    const currentAsBaseline = {
      version: currentCross.version,
      created_at: new Date().toISOString(),
      created_by: '',
      entries: [{
        data: {
          _type: 'schedule_state',
          stages: currentCross.stages || [],
          milestones: currentCross.milestones || [],
        }
      }],
    };
    renderBaselineComparison(data.baseline, currentAsBaseline, true);
  }).catch(e => alert(e.error || 'Ошибка'));
}

/**
 * Универсальное сравнение двух снимков.
 * @param {Object} left  — старый снимок (baseline JSON)
 * @param {Object} right — новый снимок (baseline JSON или виртуальный из текущего)
 * @param {boolean} rightIsCurrent — true если right = текущее состояние
 */
function renderBaselineComparison(left, right, rightIsCurrent) {
  const leftEntry = (left.entries || []).find(e => e.data && e.data._type === 'schedule_state');
  const rightEntry = (right.entries || []).find(e => e.data && e.data._type === 'schedule_state');
  const leftStages = leftEntry ? (leftEntry.data.stages || []) : [];
  const rightStages = rightEntry ? (rightEntry.data.stages || []) : [];

  // Строим map по order для сопоставления
  const leftMap = {};
  leftStages.forEach(s => { leftMap[s.order] = s; });
  const rightMap = {};
  rightStages.forEach(s => { rightMap[s.order] = s; });

  // Собираем все orders
  const allOrders = [...new Set([...Object.keys(leftMap), ...Object.keys(rightMap)])].sort((a, b) => a - b);

  const rows = allOrders.map(order => {
    const l = leftMap[order];
    const r = rightMap[order];

    if (!l && r) {
      return `<tr class="baseline-added">
        <td>${r.order}</td>
        <td>${escapeHtml(r.name)}</td>
        <td>—</td><td>—</td>
        <td>${r.date_start || '—'}</td><td>${r.date_end || '—'}</td>
        <td><span class="baseline-badge baseline-badge--added">Добавлен</span></td>
      </tr>`;
    }
    if (l && !r) {
      return `<tr class="baseline-removed">
        <td>${l.order}</td>
        <td>${escapeHtml(l.name)}</td>
        <td>${l.date_start || '—'}</td><td>${l.date_end || '—'}</td>
        <td>—</td><td>—</td>
        <td><span class="baseline-badge baseline-badge--removed">Удалён</span></td>
      </tr>`;
    }

    const changes = [];
    if (l.name !== r.name) changes.push('название');
    if (l.date_start !== r.date_start) changes.push('начало');
    if (l.date_end !== r.date_end) changes.push('окончание');

    const cls = changes.length ? 'baseline-changed' : '';
    const badge = changes.length
      ? `<span class="baseline-badge baseline-badge--changed">${escapeHtml(changes.join(', '))}</span>`
      : '<span class="baseline-badge baseline-badge--same">Без изменений</span>';

    const startCls = l.date_start !== r.date_start ? ' class="baseline-diff"' : '';
    const endCls = l.date_end !== r.date_end ? ' class="baseline-diff"' : '';

    return `<tr class="${cls}">
      <td>${r.order}</td>
      <td>${escapeHtml(r.name)}</td>
      <td>${l.date_start || '—'}</td><td>${l.date_end || '—'}</td>
      <td${startCls}>${r.date_start || '—'}</td><td${endCls}>${r.date_end || '—'}</td>
      <td>${badge}</td>
    </tr>`;
  }).join('');

  const leftDate = new Date(left.created_at).toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'});
  const rightLabel = rightIsCurrent
    ? `Текущий (v${right.version})`
    : `v${right.version}`;
  const rightDate = rightIsCurrent
    ? ''
    : ` — ${new Date(right.created_at).toLocaleString('ru-RU', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'})}`;

  let modal = document.getElementById('baselineModal');
  modal.innerHTML = `
    <div class="modal" style="max-width:960px;">
      <div class="modal-header">
        <h3>Сравнение: v${left.version} → ${rightLabel}</h3>
        <button class="modal-close" onclick="document.getElementById('baselineModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body" style="overflow-x:auto;">
        <div class="baseline-view-meta">
          <span><strong>v${left.version}:</strong> ${leftDate}</span>
          ${!rightIsCurrent ? `<span><strong>v${right.version}:</strong> ${rightDate}</span>` : ''}
        </div>
        <table class="baseline-table baseline-compare-table">
          <thead>
            <tr>
              <th rowspan="2">№</th>
              <th rowspan="2">Название</th>
              <th colspan="2" class="baseline-col-group">v${left.version}</th>
              <th colspan="2" class="baseline-col-group">${rightLabel}</th>
              <th rowspan="2">Изменение</th>
            </tr>
            <tr>
              <th>Начало</th><th>Окончание</th>
              <th>Начало</th><th>Окончание</th>
            </tr>
          </thead>
          <tbody>${rows || '<tr><td colspan="7" class="text-center text-muted">Нет данных</td></tr>'}</tbody>
        </table>
        <div style="margin-top:16px;">
          <button class="btn btn-outline btn-sm" onclick="openBaselineList()"><i class="fas fa-arrow-left"></i> Назад к списку</button>
        </div>
      </div>
    </div>
  `;
}

function deleteBaseline(id) {
  if (!confirm('Удалить снимок?')) return;
  fetchJSON(`${API}/baselines/${id}/`, { method: 'DELETE' }).then(() => {
    showToast('Снимок удалён', 'success');
    openBaselineList();
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

let _capData = { centers: [], no_center_departments: [] };
let _capFilterCenter = null; // null = все

function loadCapacity() {
  const year = document.getElementById('capacityYear').value;
  const mode = document.getElementById('capacityMode').value;
  const projectId = document.getElementById('capacityProject').value;

  let url = `${API}/capacity/?year=${year}&mode=${mode}`;
  if (projectId) url += `&project_id=${projectId}`;

  fetchJSON(url).then(data => {
    _capData = data;
    _renderCapChips(data.centers || []);
    _renderCapAll();
  }).catch(e => console.error('loadCapacity:', e));
}

function _capSetFilter(centerId) {
  _capFilterCenter = _capFilterCenter === centerId ? null : centerId;
  _renderCapAll();
}

function _renderCapChips(centers) {
  const el = document.getElementById('capCenterChips');
  if (!centers.length) { el.innerHTML = ''; return; }
  el.innerHTML = `<button class="cap-chip ${!_capFilterCenter ? 'active' : ''}" onclick="_capSetFilter(null)">Все</button>` +
    centers.map(c =>
      `<button class="cap-chip ${_capFilterCenter === c.center_id ? 'active' : ''}" onclick="_capSetFilter(${c.center_id})">${escapeHtml(c.center_name)}</button>`
    ).join('');
}

function _renderCapAll() {
  const centers = _capData.centers || [];
  const noCenterDepts = _capData.no_center_departments || [];

  // Фильтрация
  const filtered = _capFilterCenter
    ? centers.filter(c => c.center_id === _capFilterCenter)
    : centers;
  const showNoCenter = !_capFilterCenter;

  // KPI
  _renderCapKpi(filtered, showNoCenter ? noCenterDepts : []);
  // Чипы — обновляем active
  _renderCapChips(centers);
  // Карточки
  renderCapacity(filtered, showNoCenter ? noCenterDepts : []);
}

function _renderCapKpi(centers, noCenterDepts) {
  const allDepts = centers.flatMap(c => c.departments).concat(noCenterDepts);
  const totalHead = allDepts.reduce((s, d) => s + d.headcount, 0);
  const totalCap = allDepts.reduce((s, d) => s + d.capacity_hours, 0);
  const totalDem = allDepts.reduce((s, d) => s + d.demand_hours, 0);
  const avgPct = totalCap > 0 ? (totalDem / totalCap * 100) : 0;
  const overloaded = allDepts.filter(d => d.level === 'overload').length;
  const lvl = avgPct < 60 ? 'low' : avgPct < 80 ? 'normal' : avgPct <= 100 ? 'high' : 'overload';

  document.getElementById('capKpiRow').innerHTML = `
    <div class="cap-kpi"><span class="cap-kpi-label">Сотрудников</span><span class="cap-kpi-value">${totalHead}</span><span class="cap-kpi-sub">в ${allDepts.length} отд.</span></div>
    <div class="cap-kpi"><span class="cap-kpi-label">Мощность</span><span class="cap-kpi-value">${totalCap.toLocaleString('ru-RU')} ч</span></div>
    <div class="cap-kpi"><span class="cap-kpi-label">Потребность</span><span class="cap-kpi-value">${totalDem.toLocaleString('ru-RU')} ч</span></div>
    <div class="cap-kpi"><span class="cap-kpi-label">Загрузка</span><span class="cap-kpi-value cap-kpi-value--${lvl}">${avgPct.toFixed(1)}%</span></div>
    <div class="cap-kpi"><span class="cap-kpi-label">Перегрузка</span><span class="cap-kpi-value ${overloaded ? 'cap-kpi-value--overload' : ''}">${overloaded}</span><span class="cap-kpi-sub">из ${allDepts.length}</span></div>
  `;
}

function _capacityBar(d) {
  const barWidth = Math.min(d.loading_pct, 150);
  return `<div class="capacity-cell">
    <div class="loading-bar"><div class="loading-bar-fill loading-bar-fill--${d.level}" style="width:${barWidth}%"></div></div>
    <span class="capacity-pct capacity-pct--${d.level}">${d.loading_pct}%</span>
  </div>`;
}

const MONTH_NAMES = ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];

function _deptRows(departments) {
  return departments.map(d => `<tr class="cap-dept-row" onclick="showDeptDrill(${d.department_id})" style="cursor:pointer;" title="Помесячная детализация">
    <td>${escapeHtml(d.department_name)}</td>
    <td>${d.headcount}</td>
    <td>${d.capacity_hours.toLocaleString('ru-RU')}</td>
    <td>${d.demand_hours.toLocaleString('ru-RU')}</td>
    <td>${_capacityBar(d)}</td>
    <td>${levelLabel(d.level)}</td>
  </tr>`).join('');
}

let _drillChart = null;

function showDeptDrill(deptId) {
  const allDepts = (_capData.centers || []).flatMap(c => c.departments)
    .concat(_capData.no_center_departments || []);
  const dept = allDepts.find(d => d.department_id === deptId);
  if (!dept || !dept.monthly) return;

  let modal = document.getElementById('capDrillModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'capDrillModal';
    modal.className = 'modal-overlay';
    document.body.appendChild(modal);
  }

  const balance = dept.capacity_hours - dept.demand_hours;
  const balanceStr = balance >= 0
    ? `<span style="color:var(--success)">+${balance.toLocaleString('ru-RU')} ч</span>`
    : `<span style="color:var(--danger)">${balance.toLocaleString('ru-RU')} ч</span>`;

  const monthRows = dept.monthly.map(m => {
    const balM = m.balance;
    const balStr = balM >= 0
      ? `<span style="color:var(--success)">+${balM.toLocaleString('ru-RU')}</span>`
      : `<span style="color:var(--danger);font-weight:600">${balM.toLocaleString('ru-RU')}</span>`;
    const rowClass = m.level === 'overload' ? 'cap-month-over' : '';
    const barW = Math.min(m.loading_pct, 150);
    return `<tr class="${rowClass}">
      <td style="text-align:left;font-weight:500;">${MONTH_NAMES[m.month - 1]}</td>
      <td>${m.capacity.toLocaleString('ru-RU')}</td>
      <td>${m.demand.toLocaleString('ru-RU')}</td>
      <td><div class="capacity-cell">
        <div class="loading-bar" style="width:80px;"><div class="loading-bar-fill loading-bar-fill--${m.level}" style="width:${barW}%"></div></div>
        <span class="capacity-pct capacity-pct--${m.level}">${m.loading_pct}%</span>
      </div></td>
      <td>${balStr}</td>
    </tr>`;
  }).join('');

  modal.innerHTML = `
    <div class="modal-dialog" style="max-width:950px;">
      <div class="modal-header">
        <h3>${escapeHtml(dept.department_name)} — помесячная загрузка</h3>
        <button class="modal-close" onclick="document.getElementById('capDrillModal').classList.remove('open')">&times;</button>
      </div>
      <div class="modal-body">
        <div class="cap-kpi-row" style="margin-bottom:16px;">
          <div class="cap-kpi"><span class="cap-kpi-label">Численность</span><span class="cap-kpi-value">${dept.headcount}</span></div>
          <div class="cap-kpi"><span class="cap-kpi-label">Мощность (год)</span><span class="cap-kpi-value">${dept.capacity_hours.toLocaleString('ru-RU')} ч</span></div>
          <div class="cap-kpi"><span class="cap-kpi-label">Потребность (год)</span><span class="cap-kpi-value">${dept.demand_hours.toLocaleString('ru-RU')} ч</span></div>
          <div class="cap-kpi"><span class="cap-kpi-label">Загрузка</span><span class="cap-kpi-value cap-kpi-value--${dept.level}">${dept.loading_pct}%</span></div>
          <div class="cap-kpi"><span class="cap-kpi-label">Баланс</span><span class="cap-kpi-value">${balanceStr}</span></div>
        </div>
        <div class="cap-drill-toggle" style="margin-bottom:12px;">
          <button class="btn btn-sm btn-outline active" id="drillViewTable" onclick="switchDrillView('table')"><i class="fas fa-table"></i> Таблица</button>
          <button class="btn btn-sm btn-outline" id="drillViewChart" onclick="switchDrillView('chart')"><i class="fas fa-chart-bar"></i> График</button>
        </div>
        <div id="drillTableWrap">
          <table class="cap-table" style="width:100%;">
            <thead><tr>
              <th style="text-align:left;">Месяц</th>
              <th style="width:140px;">Мощность, ч</th>
              <th style="width:140px;">Потребн., ч</th>
              <th style="width:200px;">Загрузка</th>
              <th style="width:120px;">Баланс</th>
            </tr></thead>
            <tbody>${monthRows}</tbody>
          </table>
        </div>
        <div id="drillChartWrap" style="display:none;position:relative;height:320px;">
          <canvas id="drillChartCanvas"></canvas>
        </div>
      </div>
    </div>`;
  modal.classList.add('open');

  // Подготовим данные для графика (создадим при переключении)
  modal._drillMonthly = dept.monthly;
}

function switchDrillView(view) {
  const tableWrap = document.getElementById('drillTableWrap');
  const chartWrap = document.getElementById('drillChartWrap');
  const btnTable = document.getElementById('drillViewTable');
  const btnChart = document.getElementById('drillViewChart');

  if (view === 'table') {
    tableWrap.style.display = '';
    chartWrap.style.display = 'none';
    btnTable.classList.add('active');
    btnChart.classList.remove('active');
  } else {
    tableWrap.style.display = 'none';
    chartWrap.style.display = '';
    btnTable.classList.remove('active');
    btnChart.classList.add('active');
    _renderDrillChart();
  }
}

function _renderDrillChart() {
  const modal = document.getElementById('capDrillModal');
  const monthly = modal?._drillMonthly;
  if (!monthly) return;

  if (_drillChart) { _drillChart.destroy(); _drillChart = null; }

  const ctx = document.getElementById('drillChartCanvas');
  if (!ctx) return;

  const labels = monthly.map(m => MONTH_NAMES[m.month - 1].slice(0, 3));
  const demands = monthly.map(m => m.demand);
  const capacities = monthly.map(m => m.capacity);

  _drillChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Потребн. (ч)',
          data: demands,
          backgroundColor: 'rgba(59,130,246,0.5)',
          borderColor: 'rgba(59,130,246,0.8)',
          borderWidth: 1,
          borderRadius: 3,
          order: 2,
        },
        {
          label: 'Мощность (ч)',
          data: capacities,
          type: 'line',
          borderColor: '#dc2626',
          backgroundColor: 'transparent',
          borderWidth: 2,
          borderDash: [6, 3],
          pointBackgroundColor: '#dc2626',
          pointRadius: 4,
          tension: 0.1,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { usePointStyle: true, font: { size: 13 } } },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y.toLocaleString('ru-RU')} ч`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: v => v.toLocaleString('ru-RU') },
          title: { display: true, text: 'Часы', font: { size: 12 } },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

function renderCapacity(centers, noCenterDepts) {
  const container = document.getElementById('capacityCardsContainer');
  let html = '';

  centers.forEach(c => {
    const deptCount = c.departments.length;
    html += `<div class="cap-card">
      <div class="cap-card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="cap-card-title">
          <i class="fas fa-chevron-down cap-card-chevron"></i>
          <strong>${escapeHtml(c.center_name)}</strong>
          <span class="cap-dept-count">${deptCount} отд.</span>
        </div>
        <div class="cap-card-summary">
          <span class="cap-summary-item"><span class="cap-summary-label">Числ.:</span> ${c.headcount}</span>
          <span class="cap-summary-item"><span class="cap-summary-label">Мощн.:</span> ${c.capacity_hours.toLocaleString('ru-RU')} ч</span>
          <span class="cap-summary-item"><span class="cap-summary-label">Потр.:</span> ${c.demand_hours.toLocaleString('ru-RU')} ч</span>
          <span class="cap-summary-item">${_capacityBar(c)}</span>
          <span class="cap-summary-item">${levelLabel(c.level)}</span>
        </div>
      </div>
      <div class="cap-card-body">
        <table class="cap-table">
          <thead><tr>
            <th>Отдел</th>
            <th style="width:120px;">Числ.</th>
            <th style="width:180px;">Мощность, ч</th>
            <th style="width:180px;">Потребн., ч</th>
            <th style="width:220px;">Загрузка</th>
            <th style="width:140px;">Уровень</th>
          </tr></thead>
          <tbody>${_deptRows(c.departments)}</tbody>
        </table>
      </div>
    </div>`;
  });

  if (noCenterDepts.length) {
    html += `<div class="cap-card">
      <div class="cap-card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="cap-card-title">
          <i class="fas fa-chevron-down cap-card-chevron"></i>
          <strong>Без НТЦ-центра</strong>
          <span class="cap-dept-count">${noCenterDepts.length} отд.</span>
        </div>
      </div>
      <div class="cap-card-body">
        <table class="cap-table">
          <thead><tr>
            <th>Отдел</th>
            <th style="width:120px;">Числ.</th>
            <th style="width:180px;">Мощность, ч</th>
            <th style="width:180px;">Потребн., ч</th>
            <th style="width:220px;">Загрузка</th>
            <th style="width:140px;">Уровень</th>
          </tr></thead>
          <tbody>${_deptRows(noCenterDepts)}</tbody>
        </table>
      </div>
    </div>`;
  }

  container.innerHTML = html || '<div class="empty-state"><p>Нет данных о загрузке</p></div>';
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
