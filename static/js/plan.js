/// <reference path="types.js" />
// @ts-check — раскомментировать для строгой проверки типов в VS Code

/* === DJANGO CSRF / fetchJson === */
// getCsrfToken(), fetchJson() — в utils.js (единый источник)
// escapeHtml(), escapeJs() — в utils.js

/** @returns {{[key: string]: string}} */
function apiHeaders() {
  return { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() };
}
const _now = new Date();
/** @type {number} */
let selectedYear = parseInt(localStorage.getItem('plan_year') || _now.getFullYear());
/** @type {number|null} */
let selectedMonth =
  localStorage.getItem('plan_month') !== null
    ? localStorage.getItem('plan_month') === 'null'
      ? null
      : parseInt(localStorage.getItem('plan_month'))
    : _now.getMonth() + 1;
/** @type {Object<string, Array<{id: number, name: string}>>} */
let dirs = {};

// Конфигурация страницы (подставляется Django-шаблоном через JSON-блок)
/** @type {SPConfig} */
const _spCfg = JSON.parse(document.getElementById('sp-config').textContent);
/** @type {boolean} */
const IS_WRITER = _spCfg.isWriter;
/** @type {boolean} */
const IS_ADMIN = _spCfg.isAdmin;
/** @type {string} */
const USER_ROLE = _spCfg.userRole;
/** @type {string} */
const USER_DEPT = _spCfg.userDept;
/** @type {string} */
const USER_SECTOR = _spCfg.userSector;
/** @type {string} */
const USER_CENTER = _spCfg.userCenter;

// canModifyRow(), isFullAccess() — замыкания из utils.js
const _canModify = makeCanModify(_spCfg);
const _isFullAccess = makeIsFullAccess(_spCfg);

/** @type {Task[]} */
let tasks = [];
/** @type {ColSettings} */
let colSettings = _spCfg.colSettings;
/** @type {Object<number, CalendarMonth[]>} */
let _spCalCache = {}; // {year: [{month, hours_norm, ...}]}

/* ── Снимок месяца: API + рендер ─────────────────────────────────────── */

// ID задач, распределённых по корзинам снимка месяца.
// Заполняется ответом /api/analytics/month_snapshot/, используется
// для drill-down (полосы строк + фильтр-чипы).
let _snapTaskIds = {
  done: new Set(),
  done_early: new Set(),
  overdue: new Set(),
  inwork: new Set(),
  debt_closed: new Set(),
  debt_hanging: new Set(),
  unplanned: new Set(),
};

// Последний загруженный месяц в формате YYYY-MM (чтобы избежать повторных запросов)
let _snapLastMonth = null;

// Блок часов из снимка месяца: план / долг / норма / загрузка.
// Заполняется из data.hours в ответе /api/analytics/month_snapshot/.
let _snapHours = null;

// Drill-down фильтр по корзине снимка месяца (null = не активен)
/** @type {'done'|'done_early'|'overdue'|'inwork'|'debt_closed'|'debt_hanging'|'unplanned'|null} */
let _snapBucketFilter = null;

/**
 * Клик по строке снимка месяца → включает/выключает drill-down фильтр
 * по соответствующей корзине. Одна переменная (_snapBucketFilter) —
 * один источник правды для строк снимка и чипов в тулбаре.
 * @param {string} bucket
 */
function snapFilterByBucket(bucket) {
  _snapBucketFilter = _snapBucketFilter === bucket ? null : bucket;
  // Подсветка активной строки снимка и активного чипа — единый источник правды
  _syncSnapActiveUI();
  renderTable();
}

/**
 * Синхронизирует UI-подсветку корзины снимка: строки в блоке снимка
 * (.snap-row.is-linked) и чипы в тулбаре (.sp.active). Без неё клик
 * по строке не отражается на чипе и наоборот.
 */
function _syncSnapActiveUI() {
  const bucket = _snapBucketFilter || 'all';
  document.querySelectorAll('.snap-row').forEach((r) => {
    r.classList.toggle('is-linked', r.dataset.bucket === _snapBucketFilter);
  });
  document.querySelectorAll('#spStatusPanel .sp').forEach((c) => {
    c.classList.toggle('active', c.dataset.bucket === bucket);
  });
}

/**
 * Обработчик клика по чипу в тулбаре. 'all' сбрасывает drill-down,
 * остальные — делегируют в snapFilterByBucket (toggle-поведение).
 * @param {string} bucket
 */
function spFilterBucket(bucket) {
  if (bucket === 'all') {
    _snapBucketFilter = null;
    _syncSnapActiveUI();
    renderTable();
    return;
  }
  snapFilterByBucket(bucket);
}

/**
 * Привязывает обработчики клика к строкам снимка месяца.
 * Вызывается при DOMContentLoaded (разметка статическая).
 */
function _bindSnapRowClicks() {
  document.querySelectorAll('.snap-row[data-bucket]').forEach((row) => {
    row.addEventListener('click', () => snapFilterByBucket(row.dataset.bucket));
    row.style.cursor = 'pointer';
  });
}

// Снимок месяца как отдельный визуальный блок удалён — его данные дублируются
// чипами статусов. API /api/analytics/month_snapshot/ по-прежнему нужен:
// чипы читают счётчики из _snapTaskIds (заполняется ниже).

document.addEventListener('DOMContentLoaded', function () {
  _bindSnapRowClicks();
});

/**
 * Подгружает снимок месяца (данные для чипов статусов).
 * Если месяц не выбран или showAll — очищает Set'ы и прячет чипы.
 */
async function loadMonthSnapshot() {
  // Снимок — только для конкретного месяца
  if (!selectedMonth || showAll) {
    _snapLastMonth = null;
    _snapClearIds();
    // Сбросить drill-down и подсветку чипов/строк — иначе фильтр прилипает
    _snapBucketFilter = null;
    _syncSnapActiveUI();
    // Спрятать панель чипов целиком (без выбранного месяца они бессмысленны)
    const panel = document.getElementById('spStatusPanel');
    if (panel) panel.style.display = 'none';
    return;
  }

  const monthKey = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
  // При выборе ровно одного отдела — пробрасываем его в снимок.
  // При нескольких отделах — без фильтра (см. ограничение API).
  let deptCode = '';
  if (spSelectedDepts && spSelectedDepts.size === 1) {
    deptCode = [...spSelectedDepts][0];
  }

  let url = `/api/analytics/month_snapshot/?month=${monthKey}`;
  if (deptCode) url += `&dept=${encodeURIComponent(deptCode)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) {
      console.warn('month_snapshot HTTP', res.status);
      return;
    }
    const data = await res.json();
    _snapLastMonth = monthKey;
    _fillSnapTaskIds(data);
  } catch (e) {
    console.error('loadMonthSnapshot error:', e);
  }
}

function _snapClearIds() {
  for (const k of Object.keys(_snapTaskIds)) _snapTaskIds[k] = new Set();
  _snapHours = null;
}

/**
 * Заполняет Set'ы _snapTaskIds из ответа /api/analytics/month_snapshot/.
 * Используется чипами статусов для фильтрации и подсчёта.
 */
function _fillSnapTaskIds(data) {
  const mt = data.month_tasks || {};
  const d = data.debts || {};
  const ids = mt.task_ids || {};
  const dIds = d.task_ids || {};
  _snapTaskIds.done = new Set(ids.done || []);
  _snapTaskIds.done_early = new Set(ids.done_early || []);
  _snapTaskIds.overdue = new Set(ids.overdue || []);
  _snapTaskIds.inwork = new Set(ids.inwork || []);
  _snapTaskIds.debt_closed = new Set(dIds.closed || []);
  _snapTaskIds.debt_hanging = new Set(dIds.hanging || []);
  const un = data.unplanned || {};
  _snapTaskIds.unplanned = new Set(un.task_ids || []);
  _snapHours = data.hours || null;

  // Обновляем чипы в тулбаре — те же цифры, что в снимке (единый источник правды)
  spUpdateStatusPanel();
  // Переотрисовываем бейджи «часы» и «загрузка» — данные из снимка, а не локальный расчёт
  if (typeof updatePlanSummary === 'function') updatePlanSummary();

  // Применяем цветные полосы к уже отрисованным строкам таблицы,
  // не пересоздавая их целиком (чтобы не дёргать DOM лишний раз).
  _applySnapshotRowMarkers();
}

/**
 * Добавляет/удаляет классы row-month / row-debt у существующих строк
 * таблицы и обновляет бейджи статуса в ячейке «Окончание».
 * Дёшево — только classList + textContent одной span.
 */
function _applySnapshotRowMarkers() {
  const body = document.getElementById('taskBody');
  if (!body) return;
  const snapActive = selectedMonth && !showAll;
  body.querySelectorAll('tr[data-id]').forEach((tr) => {
    const id = parseInt(tr.dataset.id);
    tr.classList.remove('row-month', 'row-debt');
    const b = _snapBucketOf(id);
    if (b === 'debt_closed' || b === 'debt_hanging') tr.classList.add('row-debt');
    else if (b) tr.classList.add('row-month');

    // Если снимок активен — перекрашиваем row-done/overdue/inwork строго по корзине,
    // чтобы цвет строки и цифра в чипе/снимке совпадали.
    if (snapActive && b) {
      tr.classList.remove('row-done', 'row-early', 'row-overdue', 'row-inwork');
      if (b === 'done_early') {
        tr.classList.add('row-early');
      } else if (b === 'done' || b === 'debt_closed') {
        tr.classList.add('row-done');
      } else if (b === 'overdue' || b === 'debt_hanging') {
        tr.classList.add('row-overdue');
      } else {
        tr.classList.add('row-inwork');
      }
    }

    // Обновляем бейдж в ячейке «Окончание»
    const badge = tr.querySelector('.status-badge[data-role="snap-badge"]');
    if (badge) _fillSnapBadge(badge, b);
  });
}

/**
 * Заполняет span.status-badge нужным текстом и классом-модификатором
 * по коду корзины снимка. Если bucket=null — прячет бейдж.
 * @param {HTMLElement} el
 * @param {string|null} bucket
 */
function _fillSnapBadge(el, bucket) {
  // Сброс всех класс-модификаторов
  el.classList.remove(
    'status-badge--done',
    'status-badge--early',
    'status-badge--overdue',
    'status-badge--inwork',
    'status-badge--hanging',
  );
  if (!bucket) {
    el.style.display = 'none';
    el.textContent = '';
    return;
  }
  el.style.display = '';
  const map = {
    done: { cls: 'status-badge--done', text: '✓ Выполнено' },
    done_early: { cls: 'status-badge--early', text: '⚡ С опережением' },
    overdue: { cls: 'status-badge--overdue', text: '✗ Просрочено' },
    inwork: { cls: 'status-badge--inwork', text: '● В работе' },
    debt_closed: { cls: 'status-badge--done', text: '✓ Долг закрыт' },
    debt_hanging: { cls: 'status-badge--hanging', text: '⚠ Долг' },
  };
  const m = map[bucket];
  if (!m) {
    el.style.display = 'none';
    return;
  }
  el.classList.add(m.cls);
  el.textContent = m.text;
}

/**
 * Возвращает код корзины снимка для конкретной задачи, либо null.
 * Используется для отрисовки цветных полос строк и бейджей.
 * @param {number} taskId
 * @returns {'done'|'done_early'|'overdue'|'inwork'|'debt_closed'|'debt_hanging'|'unplanned'|null}
 */
function _snapBucketOf(taskId) {
  if (_snapTaskIds.done.has(taskId)) return 'done';
  if (_snapTaskIds.done_early.has(taskId)) return 'done_early';
  if (_snapTaskIds.overdue.has(taskId)) return 'overdue';
  if (_snapTaskIds.inwork.has(taskId)) return 'inwork';
  if (_snapTaskIds.debt_closed.has(taskId)) return 'debt_closed';
  if (_snapTaskIds.debt_hanging.has(taskId)) return 'debt_hanging';
  if (_snapTaskIds.unplanned.has(taskId)) return 'unplanned';
  return null;
}

/* ── Вспомогательные функции статусов ──────────────────────────────────
   _spGetStatus/_spTasksWithoutStatusFilter остаются для:
   - подсветки строк row-done/row-overdue/row-inwork (makeRow)
   - бейджа статуса в панели деталей (_renderActivityDetails)
   - подсчёта часов и исполнителей в summary (renderTable)
   В фильтрации они больше не участвуют — её ведёт _snapBucketFilter.
   ─────────────────────────────────────────────────────────────────── */

/**
 * Определяет простой статус задачи (3 состояния).
 * @param {Task} t
 * @returns {'done'|'overdue'|'inwork'}
 */
function _spGetStatus(t) {
  if (t.has_reports) {
    const rca = t.report_created_at ? t.report_created_at.slice(0, 10) : '';
    if (rca && selectedMonth && !showAll) {
      const endM =
        selectedMonth < 12
          ? `${selectedYear}-${String(selectedMonth + 1).padStart(2, '0')}-01`
          : `${selectedYear + 1}-01-01`;
      if (rca >= endM) return 'inwork';
    } else if (rca && !selectedMonth && !showAll) {
      const endY = `${selectedYear + 1}-01-01`;
      if (rca >= endY) return 'inwork';
    }
    return 'done';
  }
  const dl = t.deadline || t.date_end || '';
  const _today = new Date();
  const _todayStr =
    _today.getFullYear() +
    '-' +
    String(_today.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(_today.getDate()).padStart(2, '0');
  if (dl && dl.slice(0, 10) < _todayStr) return 'overdue';
  return 'inwork';
}

/**
 * Фильтрует tasks по всем colFilters (без статус-фильтра).
 * Нужно для корректного подсчёта в summary (часы/исполнители),
 * чтобы drill-down по снимку не занижал итоги.
 * @returns {Task[]}
 */
function _spTasksWithoutStatusFilter() {
  if (Object.keys(colFilters).length === 0) return tasks;
  return tasks.filter((t) => {
    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3);
        if (val.size > 0) {
          if (field === 'executor') {
            const inSingle = val.has(t.executor || '');
            const inList = (t.executors_list || []).some((ex) => val.has(ex.name || ''));
            if (!inSingle && !inList) return false;
          } else if (field === 'has_deps') {
            const label = (t.predecessors_count || 0) > 0 ? 'Со связями' : 'Без связей';
            if (!val.has(label)) return false;
          } else if (field === 'task_type') {
            if (!val.has(t.task_type || 'ПП')) return false;
          } else if (field === 'date_start' || field === 'date_end') {
            const cellVal = (t[field] || '').slice(0, 7);
            if (!val.has(cellVal)) return false;
          } else {
            if (!val.has(t[field] || '')) return false;
          }
        }
        continue;
      }
      if (col === 'plan_hours_total') {
        const total = Object.values(t.plan_hours_all || {}).reduce(
          (s, v) => s + (parseFloat(v) || 0),
          0,
        );
        const threshold = parseFloat(val);
        if (!isNaN(threshold) && total < threshold) return false;
        continue;
      }
      const cellVal = (t[col] || '').toString().toLowerCase();
      if (!cellVal.includes(val)) return false;
    }
    return true;
  });
}

/* ── Статус-панель (чипы в тулбаре) для СП ─────────────────────────────
   Цифры в чипах читаются ТОЛЬКО из _snapTaskIds (снимок месяца) —
   чтобы в чипах и блоке снимка совпадали значения (единый источник правды).
   Панель показывается только если выбран ровно один месяц (снимок активен).
   ─────────────────────────────────────────────────────────────────── */

/**
 * Обновляет счётчики в чипах тулбара на основе _snapTaskIds.
 * Если снимок не активен (нет месяца / showAll) — прячет панель.
 */
function spUpdateStatusPanel() {
  const panel = document.getElementById('spStatusPanel');
  if (!panel) return;

  // Панель имеет смысл только для конкретного месяца
  if (!selectedMonth || showAll) {
    panel.style.display = 'none';
    return;
  }
  panel.style.display = '';

  const setText = (id, v) => {
    const e = document.getElementById(id);
    if (e) e.textContent = v;
  };

  const done = _snapTaskIds.done.size;
  const early = _snapTaskIds.done_early.size;
  const overdue = _snapTaskIds.overdue.size;
  const inwork = _snapTaskIds.inwork.size;
  const debtClosed = _snapTaskIds.debt_closed.size;
  const debtHanging = _snapTaskIds.debt_hanging.size;
  const unplanned = _snapTaskIds.unplanned.size;
  const all = done + early + overdue + inwork + debtClosed + debtHanging + unplanned;

  setText('spCountAll', all);
  setText('spCountDone', done);
  setText('spCountEarly', early);
  setText('spCountOverdue', overdue);
  setText('spCountInWork', inwork);
  setText('spCountDebtClosed', debtClosed);
  setText('spCountDebt', debtHanging);
  setText('spCountUnplanned', unplanned);

  // Подсветка активного чипа
  _syncSnapActiveUI();
}

/* ── Skeleton-загрузка — skeletonRows() в utils.js ────────────────── */

/* ── Тултип для бейджа ПП (position:fixed, не обрезается overflow) ── */
const _ppTip = (() => {
  let el = null;
  function ensure() {
    if (!el) {
      el = document.createElement('div');
      el.className = 'pp-tooltip-float';
      document.body.appendChild(el);
    }
    return el;
  }
  document.addEventListener('mouseover', (e) => {
    const badge = e.target.closest('.pp-lock-badge');
    if (!badge || !badge.dataset.tooltip) return;
    const tip = ensure();
    tip.textContent = badge.dataset.tooltip;
    // Позиционируем за экраном для замера размеров
    tip.style.left = '-9999px';
    tip.style.top = '0';
    tip.classList.add('visible');
    const tw = tip.offsetWidth;
    const th = tip.offsetHeight;
    const r = badge.getBoundingClientRect();
    // Справа от бейджа, вертикально по центру
    let left = r.right + 8;
    let top = r.top + r.height / 2 - th / 2;
    // Не дать выйти за правый край — тогда слева; если и слева не влезает — прижать к левому краю
    if (left + tw > window.innerWidth - 8) left = r.left - tw - 8;
    if (left < 8) left = 8;
    if (top < 8) top = 8;
    if (top + th > window.innerHeight - 8) top = window.innerHeight - th - 8;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  });
  document.addEventListener('mouseout', (e) => {
    const badge = e.target.closest('.pp-lock-badge');
    if (!badge) return;
    if (el) el.classList.remove('visible');
  });
})();

/* ── Переключатель плотности — initDensityToggle() в utils.js ─────── */

let currentTaskId = null;
let currentTask = null;
let reportRows = [];
let pendingTaskType = null;
let newTaskExecutorsList = [];
let spSelectedDepts = new Set();
(function () {
  var saved = localStorage.getItem('sp_selected_depts');
  if (saved)
    try {
      JSON.parse(saved).forEach(function (d) {
        spSelectedDepts.add(d);
      });
    } catch (e) {
      /* ignored */
    }
  // Миграция со старого формата
  if (spSelectedDepts.size === 0) {
    var old = localStorage.getItem('sp_selected_dept');
    if (old) {
      spSelectedDepts.add(old);
      localStorage.removeItem('sp_selected_dept');
    }
  }
  // По умолчанию: начальники/замы отдела, сектора и все кроме user видят все
  // отделы (на сервере get_visibility_filter возвращает Q() для всех кроме
  // user). Только обычный user получает авто-фильтр по своему отделу.
  // Флаг show_all_depts оставлен для обратной совместимости, но теперь
  // дефолт «свой отдел» ставится только для role=user без этого флага.
  var _showAllDepts = !!(_spCfg.colSettings && _spCfg.colSettings.show_all_depts);
  var _isUserRole = USER_ROLE === 'user';
  if (spSelectedDepts.size === 0 && USER_DEPT && _isUserRole && !_showAllDepts) {
    spSelectedDepts.add(USER_DEPT);
  }
})();

const MONTH_NAMES = [
  '',
  'Янв',
  'Фев',
  'Мар',
  'Апр',
  'Май',
  'Июн',
  'Июл',
  'Авг',
  'Сен',
  'Окт',
  'Ноя',
  'Дек',
];

let showAll = false;

// ── Синхронизация фильтров СП с URL ────────────────────────────────────────
const _SP_URL_FILTER_KEYS = ['year', 'month', 'dept', 'bucket'];

function _spSyncFiltersToUrl() {
  syncFiltersToUrl({
    year: selectedYear,
    month: showAll ? 'all' : selectedMonth || null,
    dept: spSelectedDepts.size ? [...spSelectedDepts].join(',') : null,
    bucket: _snapBucketFilter || null,
  });
}

function _spRestoreFiltersFromUrl() {
  const f = readFiltersFromUrl(_SP_URL_FILTER_KEYS);
  let changed = false;
  if (f.year) {
    const y = parseInt(f.year);
    if (!isNaN(y)) {
      selectedYear = y;
      changed = true;
    }
  }
  if (f.month === 'all') {
    selectedMonth = null;
    showAll = true;
    changed = true;
  } else if (f.month && f.month !== 'null') {
    const m = parseInt(f.month);
    if (!isNaN(m) && m >= 1 && m <= 12) {
      selectedMonth = m;
      showAll = false;
      changed = true;
    }
  } else if (f.month === 'null' || ('month' in f && !f.month)) {
    selectedMonth = null;
    changed = true;
  }
  if (f.dept) {
    spSelectedDepts = new Set(f.dept.split(',').filter(Boolean));
    changed = true;
  }
  if (
    f.bucket &&
    [
      'done',
      'done_early',
      'overdue',
      'inwork',
      'debt_closed',
      'debt_hanging',
      'unplanned',
    ].includes(f.bucket)
  ) {
    _snapBucketFilter = f.bucket;
    changed = true;
  }
  return changed;
}

// ── CALENDAR ──────────────────────────────────────────────────────────────
// Подсвечивает чип текущего месяца точкой (класс .today)
function _spMarkTodayMonth() {
  var now = new Date();
  var curYear = now.getFullYear(),
    curMonth = now.getMonth() + 1;
  document.querySelectorAll('.cal-month').forEach(function (el) {
    el.classList.toggle('today', selectedYear === curYear && parseInt(el.dataset.m) === curMonth);
  });
}

function changeYear(d) {
  selectedYear += d;
  showAll = false;
  localStorage.setItem('plan_year', selectedYear);
  document.getElementById('yearDisplay').textContent = selectedYear;
  _spMarkTodayMonth();
  _spSyncFiltersToUrl();
  loadTasks();
}
function selectMonth(m) {
  if (selectedMonth === m) {
    selectedMonth = null;
  } else {
    selectedMonth = m;
  }
  showAll = false;
  document.querySelectorAll('.cal-month').forEach((el) => {
    el.classList.toggle('active', parseInt(el.dataset.m) === selectedMonth);
  });
  localStorage.setItem('plan_month', selectedMonth === null ? 'null' : selectedMonth);
  _spSyncFiltersToUrl();
  loadTasks();
}

function clearFilter() {
  selectedMonth = null;
  showAll = true;
  localStorage.setItem('plan_month', 'null');
  document.querySelectorAll('.cal-month').forEach((e) => e.classList.remove('active'));
  _spSyncFiltersToUrl();
  loadTasks();
}

// ── Пересчёт --toolbar-h по реальной высоте ──────────────────────────────
function _syncToolbarHeight() {
  var tb = document.getElementById('toolbar');
  if (!tb) return;
  // Синхронное чтение offsetHeight вызывает forced reflow — гарантирует актуальные размеры
  var h = tb.offsetHeight;
  document.documentElement.style.setProperty('--toolbar-h', h + 'px');
}

// ── DEPT FILTER (через shared-toolbar.js) ────────────────────────────────
let _spDeptFilter = null;

function initDeptChips() {
  // Источник списка отделов — серверный список ВСЕХ отделов (_spCfg.deptCodes),
  // а не список из загруженных задач. Иначе, если пользователь видит только
  // свой отдел в данных, в dropdown будет одна строка и выбрать чужой отдел
  // станет невозможно.
  var allDepts =
    _spCfg.deptCodes && _spCfg.deptCodes.length
      ? _spCfg.deptCodes.slice()
      : [...new Set(tasks.map((t) => t.dept).filter(Boolean))];
  var depts = allDepts.sort(function (a, b) {
    return String(a).localeCompare(String(b), 'ru');
  });
  // Убираем несуществующие отделы из выбора (защита от мусора в localStorage)
  var cleaned = new Set(
    [...spSelectedDepts].filter(function (d) {
      return depts.includes(d);
    }),
  );
  if (cleaned.size !== spSelectedDepts.size) {
    spSelectedDepts = cleaned;
    _saveSPDepts();
  }
  // Если < 2 отделов в данных, не перезатираем ранний dropdown из конфига
  if (depts.length < 2 && _spDeptFilter) {
    _syncDeptFilter();
    return;
  }
  _spDeptFilter = initDeptFilter({
    barId: 'deptBar',
    wrapId: 'spDeptWrap',
    idPrefix: 'sp',
    multiSelect: true,
    depts: depts,
    getSelection: function () {
      return spSelectedDepts;
    },
    setSelection: function (sel) {
      spSelectedDepts = sel;
      _saveSPDepts();
    },
    onApply: function () {
      _syncDeptFilter();
      renderTable();
      // Снимок месяца зависит от выбранного отдела — обновляем цифры чипов
      loadMonthSnapshot();
      _spSyncFiltersToUrl();
      _syncToolbarHeight();
      // Сбросить бейдж ошибок планирования — при смене скоупа цифра устаревает
      _resetPlanningErrorsBadge();
    },
  });
  _syncDeptFilter();
  _syncToolbarHeight();
}

function _saveSPDepts() {
  if (spSelectedDepts.size)
    localStorage.setItem('sp_selected_depts', JSON.stringify([...spSelectedDepts]));
  else localStorage.removeItem('sp_selected_depts');
}

function _syncDeptFilter() {
  const btn = document.querySelector('.mf-trigger[data-col="dept"]');
  if (spSelectedDepts.size > 0) {
    mfSelections['dept'] = new Set(spSelectedDepts);
    colFilters['mf_dept'] = new Set(spSelectedDepts);
    if (btn) {
      if (!btn.classList.contains('mf-icon'))
        btn.textContent =
          spSelectedDepts.size === 1 ? [...spSelectedDepts][0] : spSelectedDepts.size + ' отд.';
      btn.classList.add('active');
    }
  } else {
    delete colFilters['mf_dept'];
    mfSelections['dept'] = new Set();
    if (btn) {
      if (!btn.classList.contains('mf-icon')) btn.textContent = MF_DEFAULTS['dept'] || '▼';
      btn.classList.remove('active');
    }
  }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').classList.toggle('visible', hasFilters);
}

// toggleNavDropdown — определена в base.html

window.addEventListener('DOMContentLoaded', async () => {
  // Sidebar dropdowns и scroll — управляется base.html

  // Delegated focus/blur for active row highlight
  document.addEventListener('focusin', function (e) {
    if (e.target.closest && e.target.closest('.data-table td')) setActiveRow(e.target);
  });
  document.addEventListener('focusout', function (e) {
    if (e.target.closest && e.target.closest('.data-table td')) {
      setTimeout(function () {
        var active = document.activeElement;
        if (!active || !active.closest || !active.closest('.data-table td')) clearActiveRow();
      }, 50);
    }
  });

  // Регистрируем кастомные close-функции для модалок со сбросом состояния
  // ESC/click обрабатываются глобально в utils.js/modal.js
  registerModalCloser('newTaskModal', function () {
    closeNewTaskModal();
  });
  registerModalCloser('reportModal', function () {
    closeReportModal();
  });
  registerModalCloser('depsModal', function () {
    closeDepsModal();
  });

  // Tooltip для бейджей типа задачи — используем нативный title (не зависает)

  // Восстанавливаем фильтры из URL (для расшаренных ссылок) — URL приоритетнее localStorage
  _spRestoreFiltersFromUrl();

  document.getElementById('yearDisplay').textContent = selectedYear;
  _spMarkTodayMonth();
  if (selectedMonth) {
    const el = document.querySelector(`.cal-month[data-m="${selectedMonth}"]`);
    if (el) el.classList.add('active');
  }
  const si = document.getElementById('searchInput');
  si.value = '';
  // Brave/Chrome autocomplete может подставить значение после DOMContentLoaded
  setTimeout(function () {
    si.value = '';
  }, 50);
  initViewModeToggle(
    '#spViewModeToggle',
    '.table-wrap',
    (colSettings && colSettings.sp_view_mode) || 'full',
    { hiddenMap: _VM_HIDDEN_SP, settingKey: 'sp_view_mode', cssPrefix: 'sp-view' },
  );
  // Ранний рендер dept-dropdown из серверных данных (без ожидания loadTasks)
  if (_spCfg.deptCodes && _spCfg.deptCodes.length > 1) {
    _spDeptFilter = initDeptFilter({
      barId: 'deptBar',
      wrapId: 'spDeptWrap',
      idPrefix: 'sp',
      multiSelect: true,
      depts: _spCfg.deptCodes,
      getSelection: function () {
        return spSelectedDepts;
      },
      setSelection: function (sel) {
        spSelectedDepts = sel;
        _saveSPDepts();
      },
      onApply: function () {
        _syncDeptFilter();
        renderTable();
        // Снимок месяца зависит от выбранного отдела — обновляем цифры чипов
        loadMonthSnapshot();
        _spSyncFiltersToUrl();
        _syncToolbarHeight();
        // Сбросить бейдж ошибок планирования — при смене скоупа цифра устаревает
        _resetPlanningErrorsBadge();
      },
    });
    _syncDeptFilter();
  }
  _syncToolbarHeight();
  var _resizePending = false;
  window.addEventListener('resize', function () {
    if (!_resizePending) {
      _resizePending = true;
      requestAnimationFrame(function () {
        _syncToolbarHeight();
        _resizePending = false;
      });
    }
  });
  // ResizeObserver — автоматически пересчитывает --toolbar-h при изменении размера тулбара (dept chips и т.д.)
  if (window.ResizeObserver) {
    var _tbEl = document.getElementById('toolbar');
    if (_tbEl) new ResizeObserver(_syncToolbarHeight).observe(_tbEl);
  }
  await loadDirs();
  await loadTasks();
  _syncToolbarHeight(); // после loadTasks — dept chips уже отрисованы
  // Listener после первого loadTasks, чтобы setTimeout-очистки не вызвали повторную загрузку
  si.addEventListener(
    'input',
    debounce(() => loadTasks(), 300),
  );
  initColResize();
  applyColSettings();
  initFilterMode();
  _spInitSort();
  runMonthCheckIfNeeded();
  // Drag-and-drop сортировка строк (перетаскивание за ⋮⋮ ручку)
  if (typeof initDragSort === 'function') {
    initDragSort('#mainTable', {
      onReorder: function (order) {
        // Обновляем нумерацию строк после перетаскивания
        order.forEach(function (item) {
          var numTd = item.el.querySelector('td[data-col-idx="0"]');
          if (numTd) numTd.textContent = item.index + 1;
        });
      },
    });
  }
  // Ошибки планирования проверяются только по запросу пользователя (кнопка)
});

// ── TASKS ─────────────────────────────────────────────────────────────────
var SP_FETCH_CHUNK = 200;
var _spBgLoading = false;

function _spBuildUrl() {
  var search = document.getElementById('searchInput').value.trim();
  var url;
  if (showAll) {
    url = '/api/tasks/?all=1';
  } else {
    url = '/api/tasks/?year=' + selectedYear;
    if (selectedMonth) url += '&month=' + selectedMonth;
  }
  if (search) url += '&search=' + encodeURIComponent(search);
  return url;
}

async function loadTasks() {
  // Сброс закреплённой строки (пин живёт один цикл загрузки)
  if (_spPinKeep) {
    _spPinKeep = false;
  } else {
    _spPinnedRowId = null;
  }
  _spBgLoading = false;

  // Бейдж ошибок планирования устаревает при любой смене фильтров
  // (год/месяц/отделы/«Показать всё») — сбрасываем к исходному виду.
  if (typeof _resetPlanningErrorsBadge === 'function') _resetPlanningErrorsBadge();

  var baseUrl = _spBuildUrl();

  document.getElementById('taskBody').innerHTML = skeletonRows(10, 15);
  document.getElementById('searchCount').textContent = '...';

  try {
    // Загружаем первую порцию + кеш календаря (параллельно)
    var resProm = fetch(baseUrl + '&limit=' + SP_FETCH_CHUNK + '&offset=0');
    var calYear = selectedYear || new Date().getFullYear();
    var calProm = _spCalCache[calYear]
      ? Promise.resolve(_spCalCache[calYear])
      : fetch('/api/work_calendar/?year=' + calYear)
          .then(function (r) {
            return r.ok ? r.json() : [];
          })
          .catch(function () {
            return [];
          });
    var [res, calData] = await Promise.all([resProm, calProm]);
    if (!res.ok) {
      console.error('loadTasks HTTP error:', res.status);
      return;
    }
    tasks = await res.json();
    _spCalCache[calYear] = calData;

    initDeptChips();
    initMfTriggers();
    renderTable();

    // Снимок месяца — параллельно, не блокирует рендер таблицы
    loadMonthSnapshot();

    // Дозагрузка в фоне если есть ещё
    var hasMore = res.headers.get('X-Has-More') === 'true';
    if (hasMore) {
      _spBgLoading = true;
      _spBgLoadRemaining(baseUrl, tasks.length);
    }
  } catch (e) {
    console.error('loadTasks error:', e);
    document.getElementById('searchCount').textContent = 'Ошибка загрузки';
  }
}

// Подсветка строки при переходе с дашборда (?highlight=<task_id>)
// Фоновая дозагрузка оставшихся строк порциями
async function _spBgLoadRemaining(baseUrl, offset) {
  // eslint-disable-next-line no-constant-condition
  while (true) {
    var url = baseUrl + '&limit=' + SP_FETCH_CHUNK + '&offset=' + offset;
    var resp;
    try {
      resp = await fetch(url);
    } catch (e) {
      break;
    }
    if (!resp.ok) break;

    var batch = await resp.json();
    if (!Array.isArray(batch) || batch.length === 0) break;

    tasks = tasks.concat(batch);
    offset += batch.length;

    // Перерисовываем с новыми данными
    renderTable();

    var hasMore = resp.headers.get('X-Has-More') === 'true';
    if (!hasMore) break;
  }
  _spBgLoading = false;
  // После полной дозагрузки — обновить чипы отделов (могли появиться новые)
  initDeptChips();
}

// ══════════════════════════════════════════════════════════════════════════
// PLANNING ERRORS
// ══════════════════════════════════════════════════════════════════════════
// ОШИБКИ ПЛАНИРОВАНИЯ
// Проверяются только по запросу пользователя (кнопка «Ошибки планирования»)
// ══════════════════════════════════════════════════════════════════════════
const DEFAULT_MONTH_NORM = 168; // ч/мес если в производственном календаре не задано

/**
 * Нормализует ФИО: «Иванов Иван Иванович» → «Иванов И.И.»
 * Если уже в коротком формате — возвращает как есть.
 * @param {string} name
 * @returns {string}
 */
function _toShortName(name) {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 3) return parts[0] + ' ' + parts[1][0] + '.' + parts[2][0] + '.';
  if (parts.length === 2 && !parts[1].includes('.')) return parts[0] + ' ' + parts[1][0] + '.';
  return name;
}
const PE_IGNORE_KEY = 'pe_ignored_v2'; // ключ localStorage для игнорируемых ошибок

// Хранилище игнорируемых ошибок: { [errKey]: true }
function peGetIgnored() {
  try {
    return JSON.parse(localStorage.getItem(PE_IGNORE_KEY) || '{}');
  } catch {
    return {};
  }
}
function peSetIgnored(key) {
  const d = peGetIgnored();
  d[key] = true;
  localStorage.setItem(PE_IGNORE_KEY, JSON.stringify(d));
}
function peIsIgnored(key) {
  return !!peGetIgnored()[key];
}

async function calcPlanningErrors() {
  const now = new Date();
  // Используем выбранный период, а не текущую дату
  const curYear = selectedYear || now.getFullYear();
  const curMonth = selectedMonth || now.getMonth() + 1;
  const curKey = `${curYear}-${String(curMonth).padStart(2, '0')}`;
  const todayStr = now.toISOString().slice(0, 10);
  // MONTHS_FULL — в utils.js

  // Кеш ignored — парсим localStorage один раз (не на каждый вызов peIsIgnored)
  const _ignored = peGetIgnored();
  const isIgn = (key) => !!_ignored[key];

  // Параллельная загрузка данных (tasks + calendar + vacations одновременно)
  let allTasks, calData, vacData;
  const tasksPromise =
    !showAll && selectedYear === curYear && selectedMonth === curMonth && tasks.length > 0
      ? Promise.resolve(tasks)
      : fetch(`/api/tasks/?year=${curYear}&month=${curMonth}`)
          .then((r) => (r.ok ? r.json() : []))
          .catch(() => []);

  const calPromise = fetch(`/api/work_calendar/?year=${curYear}`)
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => []);
  const vacPromise = fetch(`/api/vacations/?year=${curYear}`)
    .then((r) => (r.ok ? r.json() : []))
    .catch(() => []);

  [allTasks, calData, vacData] = await Promise.all([tasksPromise, calPromise, vacPromise]);

  // Скоуп подразделения = тот же, что и в СП-таблице (spSelectedDepts).
  // По умолчанию там стоит отдел/сектор/центр по роли (см. initDeptChips),
  // но пользователь может вручную расширить/поменять выбор через чипы.
  // Для роли user — бэк уже вернул только его скоуп (get_visibility_filter).
  if (spSelectedDepts && spSelectedDepts.size > 0) {
    allTasks = allTasks.filter((t) => spSelectedDepts.has(t.dept));
  }

  // Норма рабочего времени из производственного календаря
  let monthNorm = DEFAULT_MONTH_NORM;
  const calEntry = calData.find((c) => c.month === curMonth);
  if (calEntry && calEntry.hours_norm) monthNorm = calEntry.hours_norm;

  // Фильтруем отпуска: пересекаются с текущим месяцем
  const monthStartStr = `${curYear}-${String(curMonth).padStart(2, '0')}-01`;
  const monthEndStr = `${curYear}-${String(curMonth).padStart(2, '0')}-31`;
  let vacations = vacData.filter((v) => v.date_start <= monthEndStr && v.date_end >= monthStartStr);

  // ── 1. Просроченные задачи и долги ──────────────────────────────────────
  // Берём из снимка месяца (_snapTaskIds), чтобы определения совпадали
  // с чипами тулбара — единый источник правды на сервере.
  //   overdue       — дедлайн в этом месяце, уже наступил, отчёта нет
  //   debt_hanging  — дедлайн до начала месяца, отчёта нет
  // Если снимок ещё не загружен (первый клик до ответа API) — откатываемся
  // на клиентскую логику, чтобы модалка не падала.
  const _snapReady =
    _snapLastMonth === curKey &&
    (_snapTaskIds.overdue.size > 0 ||
      _snapTaskIds.debt_hanging.size > 0 ||
      _snapTaskIds.inwork.size > 0);

  let overdue, debts;
  if (_snapReady) {
    overdue = allTasks.filter((t) => _snapTaskIds.overdue.has(t.id) && !isIgn(`overdue_${t.id}`));
    debts = allTasks.filter((t) => _snapTaskIds.debt_hanging.has(t.id) && !isIgn(`debt_${t.id}`));
  } else {
    // Fallback: клиентский расчёт (используется, только если снимок не успел
    // загрузиться; цифры могут слегка расходиться с чипами — это временно).
    const _hasHoursInPeriod = (t) => {
      const exList = t.executors_list || [];
      if (exList.length > 0) {
        return exList.some((ex) => parseFloat((ex.hours || {})[curKey] || 0) > 0);
      }
      const ph = t.plan_hours_all || {};
      return parseFloat(ph[curKey] || 0) > 0;
    };
    const overdueAll = allTasks.filter((t) => {
      const de = t.date_end ? t.date_end.slice(0, 10) : null;
      const dead = t.deadline ? t.deadline.slice(0, 10) : null;
      const isOverdue = (de && de < todayStr) || (dead && dead < todayStr);
      return isOverdue && !t.has_reports;
    });
    overdue = overdueAll.filter((t) => _hasHoursInPeriod(t) && !isIgn(`overdue_${t.id}`));
    debts = overdueAll.filter((t) => !_hasHoursInPeriod(t) && !isIgn(`debt_${t.id}`));
  }

  // ── 2. Задачи с датами уже просроченными при создании ────────────────────
  const badDates = allTasks.filter((t) => {
    const ds = t.date_start ? t.date_start.slice(0, 10) : null;
    const de = t.date_end ? t.date_end.slice(0, 10) : null;
    const dead = t.deadline ? t.deadline.slice(0, 10) : null;
    if (!ds) return false;
    return ((de && ds > de) || (dead && ds > dead)) && !isIgn(`baddates_${t.id}`);
  });

  // ── 3. Загрузка сотрудников (перегруз/недогруз) ──────────────────────────
  // Имена нормализуются в короткий формат (Фамилия И.О.) для сопоставления
  // со справочником сотрудников (dirs._ids_employees).
  const execLoad = {};
  allTasks.forEach((t) => {
    const execList = t.executors_list || [];
    if (execList.length > 0) {
      execList.forEach((ex) => {
        if (!ex.name) return;
        const shortN = _toShortName(ex.name);
        const hours = parseFloat((ex.hours || {})[curKey] || 0);
        execLoad[shortN] = (execLoad[shortN] || 0) + hours;
      });
    } else if (t.executor) {
      const shortN = _toShortName(t.executor);
      const ph = t.plan_hours_all || {};
      const hours = parseFloat(ph[curKey] || 0);
      execLoad[shortN] = (execLoad[shortN] || 0) + hours;
    }
  });

  const threshold = monthNorm * 1.1;
  const overloaded = [];
  const underloaded = [];

  Object.entries(execLoad).forEach(([name, hours]) => {
    if (hours > threshold && !isIgn(`overload_${name}_${curKey}`)) {
      overloaded.push({ name, hours });
    }
  });

  // Недозагруженные — ВСЕ сотрудники, учитываем отпуска
  const _monthStart = new Date(curYear, curMonth - 1, 1);
  const _monthEnd = new Date(curYear, curMonth, 0);
  const _totalDays = _monthEnd.getDate();
  const _vacDays = {};
  vacations.forEach((v) => {
    const name = _toShortName(v.executor || v.executor_name || '');
    if (!name) return;
    const vs = new Date(Math.max(new Date(v.date_start), _monthStart));
    const ve = new Date(Math.min(new Date(v.date_end), _monthEnd));
    if (vs <= ve) {
      const days = Math.round((ve - vs) / 86400000) + 1;
      _vacDays[name] = (_vacDays[name] || 0) + days;
    }
  });

  // Сотрудники для проверки недозагрузки — по тому же скоупу отделов, что и задачи.
  // Иначе «Недозагруженные» показывает сотрудников чужих отделов.
  let _empSource = dirs['_ids_employees'] || [];
  if (spSelectedDepts && spSelectedDepts.size > 0) {
    _empSource = _empSource.filter((e) => e.dept && spSelectedDepts.has(e.dept));
  }
  const _allEmps = new Set(_empSource.map((e) => e.value));
  _allEmps.forEach((name) => {
    const hours = execLoad[name] || 0;
    const vacD = _vacDays[name] || 0;
    const adjNorm = vacD >= _totalDays ? 0 : monthNorm * (1 - vacD / _totalDays);
    if (adjNorm > 0 && hours < adjNorm && !isIgn(`underload_${name}_${curKey}`)) {
      underloaded.push({ name, hours, norm: Math.round(adjNorm) });
    }
  });

  // ── 4. Отпуска сотрудников с запланированными задачами ───────────────────
  // Предварительный Set исполнителей (нормализованные имена)
  const _execInTasks = new Set();
  allTasks.forEach((t) => {
    (t.executors_list || []).forEach((ex) => {
      if (ex.name) _execInTasks.add(_toShortName(ex.name));
    });
    if (t.executor) _execInTasks.add(_toShortName(t.executor));
  });

  const vacConflicts = [];
  vacations.forEach((v) => {
    const name = _toShortName(v.executor || v.executor_name || '');
    if (!name) return;
    const ignKey = `vacation_${name}_${v.date_start}`;
    if (isIgn(ignKey)) return;
    if (_execInTasks.has(name)) vacConflicts.push({ ...v, name, ignKey });
  });

  // ── 5. Разбивка ошибок по отделам ─────────────────────────────────────
  // В API задача сериализуется с полем `dept` (код отдела), не `department`.
  const deptStats = {};
  overdue.forEach((t) => {
    const d = t.dept || '—';
    if (!deptStats[d]) deptStats[d] = { danger: 0, debt: 0, warn: 0 };
    deptStats[d].danger++;
  });
  debts.forEach((t) => {
    const d = t.dept || '—';
    if (!deptStats[d]) deptStats[d] = { danger: 0, debt: 0, warn: 0 };
    deptStats[d].debt++;
  });
  underloaded.forEach((e) => {
    // underloaded не имеет department — пропускаем
  });
  badDates.forEach((t) => {
    const d = t.dept || '—';
    if (!deptStats[d]) deptStats[d] = { danger: 0, debt: 0, warn: 0 };
    deptStats[d].warn++;
  });
  // Сортируем по общему количеству ошибок (убывание)
  const deptBreakdown = Object.entries(deptStats)
    .map(([name, v]) => ({
      name,
      danger: v.danger,
      debt: v.debt,
      warn: v.warn,
      total: v.danger + v.debt + v.warn,
    }))
    .sort((a, b) => b.total - a.total);

  // ── 6. Прогноз: дедлайны в ближайшие 7 дней ────────────────────────────
  const _7days = new Date(now.getTime() + 7 * 86400000).toISOString().slice(0, 10);
  const soonExpiring = allTasks.filter((t) => {
    const de = t.date_end ? t.date_end.slice(0, 10) : null;
    const dead = t.deadline ? t.deadline.slice(0, 10) : null;
    const d = de || dead;
    return d && d >= todayStr && d <= _7days && !t.has_reports;
  });
  const soonNoExec = soonExpiring.filter(
    (t) => !t.executor && !(t.executors_list && t.executors_list.length),
  );

  // ── 7. Таймлайн: дедлайны по дням месяца ───────────────────────────────
  const daysInMonth = new Date(curYear, curMonth, 0).getDate();
  const dayDeadlines = new Array(daysInMonth).fill(0);
  const dayOverdue = new Array(daysInMonth).fill(0);
  allTasks.forEach((t) => {
    const de = t.date_end ? t.date_end.slice(0, 10) : null;
    const dead = t.deadline ? t.deadline.slice(0, 10) : null;
    const d = de || dead;
    if (!d) return;
    const dp = new Date(d);
    if (dp.getFullYear() === curYear && dp.getMonth() + 1 === curMonth) {
      const dayIdx = dp.getDate() - 1;
      dayDeadlines[dayIdx]++;
      if (d < todayStr && !t.has_reports) dayOverdue[dayIdx]++;
    }
  });

  return {
    overdue,
    debts,
    badDates,
    overloaded,
    underloaded,
    vacConflicts,
    curYear,
    curMonth,
    curKey,
    todayStr,
    monthNorm,
    MONTHS_FULL,
    deptBreakdown,
    soonExpiring,
    soonNoExec,
    dayDeadlines,
    dayOverdue,
    daysInMonth,
    totalTasks: allTasks.length,
  };
}

// Сбрасывает бейдж «Ошибки планирования» к исходному виду —
// вызывается при смене скоупа (отделы/год/месяц), чтобы цифра не вводила в заблуждение.
function _resetPlanningErrorsBadge() {
  const btn = document.getElementById('errorsBtn');
  if (!btn) return;
  btn.innerHTML = '⚠️ Ошибки планирования';
  btn.className = 'topbar-btn errors';
  btn.disabled = false;
}

async function refreshPlanningErrors() {
  const btn = document.getElementById('errorsBtn');
  btn.disabled = true;
  btn.innerHTML = '⏳ Проверка...';
  btn.className = 'topbar-btn errors';

  // Убедимся, что снимок месяца загружен — модалка ошибок берёт оттуда
  // просроченные/долги, чтобы цифры совпадали с чипами тулбара.
  const _curKey =
    selectedMonth && !showAll ? `${selectedYear}-${String(selectedMonth).padStart(2, '0')}` : null;
  if (_curKey && _snapLastMonth !== _curKey) {
    await loadMonthSnapshot();
  }

  const result = await calcPlanningErrors();
  const total =
    result.overdue.length +
    result.debts.length +
    result.badDates.length +
    result.overloaded.length +
    result.underloaded.length +
    result.vacConflicts.length;

  if (total === 0) {
    btn.textContent = '✓ Нет ошибок';
    btn.className = 'topbar-btn errors no-errors';
  } else {
    btn.innerHTML = `⚠️ Ошибки планирования <span class="err-badge">${total}</span>`;
    btn.className = 'topbar-btn errors has-errors';
  }
  btn.disabled = false;
  return { ...result, total };
}

async function openPlanningErrors() {
  document.getElementById('peViz').innerHTML = '';
  document.getElementById('peBody').innerHTML =
    '<div style="padding:30px;text-align:center;color:var(--muted)">⏳ Анализ данных...</div>';
  document.getElementById('peModal').classList.add('open');

  const result = await refreshPlanningErrors();
  const {
    overdue,
    debts,
    badDates,
    overloaded,
    underloaded,
    vacConflicts,
    curYear,
    curMonth,
    curKey,
    total,
    monthNorm,
    MONTHS_FULL,
    todayStr,
    deptBreakdown,
    soonExpiring,
    soonNoExec,
    dayDeadlines,
    dayOverdue,
    daysInMonth,
    totalTasks,
  } = result;

  // Скоуп подразделения: тот же, что и в СП-таблице
  let _peScope = 'Все отделы';
  if (spSelectedDepts && spSelectedDepts.size > 0) {
    _peScope =
      spSelectedDepts.size === 1
        ? `Отдел ${[...spSelectedDepts][0]}`
        : `${spSelectedDepts.size} отд.`;
  }
  document.getElementById('peMeta').textContent =
    `${MONTHS_FULL[curMonth]} ${curYear} · ${_peScope} · Норма: ${monthNorm} ч/мес`;
  document.getElementById('peLastCheck').textContent =
    'Проверено: ' + new Date().toLocaleTimeString('ru-RU');

  const viz = document.getElementById('peViz');
  viz.innerHTML = '';
  const body = document.getElementById('peBody');
  body.innerHTML = '';

  // ── Кольцо здоровья + полосы ─────────────────────────────────────────────
  const healthPct = totalTasks > 0 ? Math.round(((totalTasks - total) / totalTasks) * 100) : 100;
  const circumference = 2 * Math.PI * 42; // ≈264
  const offset = circumference - (circumference * healthPct) / 100;
  const ringColor = healthPct >= 80 ? 'var(--ok)' : healthPct >= 50 ? '#f59e0b' : 'var(--danger)';
  const ringTextColor = healthPct >= 80 ? '#22c55e' : healthPct >= 50 ? '#f59e0b' : 'var(--danger)';

  const barMax = Math.max(
    overdue.length,
    debts.length,
    badDates.length,
    overloaded.length,
    underloaded.length,
    vacConflicts.length,
    1,
  );
  const barPct = (n) => Math.max(3, Math.round((n / barMax) * 100));
  const barCls = (n, threshDanger) => (n > 0 ? (n >= threshDanger ? 'danger' : 'warn') : 'ok');

  const vcTop = document.createElement('div');
  vcTop.className = 'vc-top';
  vcTop.innerHTML = `
    <div class="vc-score">
      <div class="vc-ring">
        <svg viewBox="0 0 100 100" width="100" height="100">
          <circle cx="50" cy="50" r="42" fill="none" stroke="#e2e8f0" stroke-width="10"/>
          <circle cx="50" cy="50" r="42" fill="none" stroke="${ringColor}" stroke-width="10"
            stroke-dasharray="${circumference.toFixed(0)}" stroke-dashoffset="${offset.toFixed(0)}" stroke-linecap="round"/>
        </svg>
        <div class="vc-ring-text" style="color:${ringTextColor}">${healthPct}%</div>
      </div>
      <div class="vc-score-label">Здоровье плана</div>
      <div class="vc-score-sub">${total} ошибок из ${totalTasks} задач</div>
    </div>
    <div class="vc-bars">
      <div class="vc-bar-row"><span class="vc-bar-label">Просроченные</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(overdue.length, 10)}" style="width:${barPct(overdue.length)}%">${overdue.length}</div></div></div>
      <div class="vc-bar-row"><span class="vc-bar-label">Долги</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(debts.length, 10)}" style="width:${barPct(debts.length)}%">${debts.length}</div></div></div>
      <div class="vc-bar-row"><span class="vc-bar-label">Ошибки в датах</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(badDates.length, 5)}" style="width:${barPct(badDates.length)}%">${badDates.length}</div></div></div>
      <div class="vc-bar-row"><span class="vc-bar-label">Перегруженные</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(overloaded.length, 5)}" style="width:${barPct(overloaded.length)}%">${overloaded.length}</div></div></div>
      <div class="vc-bar-row"><span class="vc-bar-label">Недозагруженные</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(underloaded.length, 10)}" style="width:${barPct(underloaded.length)}%">${underloaded.length}</div></div></div>
      <div class="vc-bar-row"><span class="vc-bar-label">Конфликт отпусков</span><div class="vc-bar-track"><div class="vc-bar-fill ${barCls(vacConflicts.length, 5)}" style="width:${barPct(vacConflicts.length)}%">${vacConflicts.length}</div></div></div>
    </div>`;
  viz.appendChild(vcTop);

  // ── Прогноз (ближайшие 7 дней) ──────────────────────────────────────────
  if (soonExpiring.length > 0) {
    const fc = document.createElement('div');
    fc.className = 'forecast-bar';
    fc.style.cursor = 'pointer';
    const noExecMsg = soonNoExec.length > 0 ? `, из них ${soonNoExec.length} без исполнителя` : '';
    fc.innerHTML = `<span class="forecast-icon">⏰</span>
      <span class="forecast-text">В ближайшие <strong>7 дней</strong> истекает срок у <strong>${soonExpiring.length} работ</strong>${escapePe(noExecMsg)} <span style="opacity:.6;font-size:12px">· нажмите для подробностей</span></span>
      <span class="forecast-badge">+${soonExpiring.length}</span>`;
    fc.addEventListener('click', () => {
      const sec = document.getElementById('peSoonExpiring');
      if (sec) {
        sec.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const secBody = sec.querySelector('.va-sec-body');
        if (secBody && !secBody.classList.contains('open')) {
          secBody.classList.add('open');
          sec.querySelector('.va-sec-arrow').textContent = '▲';
        }
      }
    });
    viz.appendChild(fc);
  }

  // ── Разбивка по отделам ──────────────────────────────────────────────────
  if (deptBreakdown.length > 0) {
    const maxDept = deptBreakdown[0].total;
    const deptDiv = document.createElement('div');
    deptDiv.className = 'dept-breakdown';
    let rowsHtml = deptBreakdown
      .slice(0, 6)
      .map((d) => {
        const dPct = maxDept > 0 ? Math.round((d.danger / maxDept) * 100) : 0;
        const debtPct = maxDept > 0 ? Math.round((d.debt / maxDept) * 100) : 0;
        const wPct = maxDept > 0 ? Math.round((d.warn / maxDept) * 100) : 0;
        return `<div class="dept-row">
        <span class="dept-name">${escapePe(d.name)}</span>
        <div class="dept-bar-track">
          ${d.danger > 0 ? `<div class="dept-bar-seg danger" style="width:${dPct}%">${d.danger}</div>` : ''}
          ${d.debt > 0 ? `<div class="dept-bar-seg debt" style="width:${debtPct}%;background:#9333ea">${d.debt}</div>` : ''}
          ${d.warn > 0 ? `<div class="dept-bar-seg warn" style="width:${wPct}%">${d.warn}</div>` : ''}
        </div>
        <span class="dept-total">${d.total}</span>
      </div>`;
      })
      .join('');
    deptDiv.innerHTML = `<div class="dept-breakdown-title">Ошибки по отделам</div>
      <div class="dept-rows">${rowsHtml}</div>
      <div class="timeline-legend" style="margin-top:8px">
        <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:var(--danger)"></span> Просрочено</span>
        <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:#9333ea"></span> Долги</span>
        <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:#f59e0b"></span> Ошибки дат</span>
      </div>`;
    viz.appendChild(deptDiv);
  }

  // ── Таймлайн дедлайнов по дням ───────────────────────────────────────────
  const maxDay = Math.max(...dayDeadlines, 1);
  const todayDay = new Date().getDate();
  const todayMonth = new Date().getMonth() + 1;
  const todayYear = new Date().getFullYear();
  const isCurrentMonth = curYear === todayYear && curMonth === todayMonth;

  const tlDiv = document.createElement('div');
  tlDiv.className = 'timeline-panel';
  let daysHtml = '',
    labelsHtml = '';
  for (let i = 0; i < daysInMonth; i++) {
    const dt = new Date(curYear, curMonth - 1, i + 1);
    const isWeekend = dt.getDay() === 0 || dt.getDay() === 6;
    const hPct = Math.max(5, Math.round((dayDeadlines[i] / maxDay) * 100));
    const isToday = isCurrentMonth && i + 1 === todayDay;
    let bg;
    if (isWeekend && dayDeadlines[i] === 0) {
      bg = 'var(--muted);opacity:0.3';
    } else if (dayOverdue[i] > 0) {
      bg = 'var(--danger)';
    } else if (
      dayDeadlines[i] > 0 &&
      isCurrentMonth &&
      i + 1 <= todayDay + 7 &&
      i + 1 >= todayDay
    ) {
      bg = '#f59e0b';
    } else if (dayDeadlines[i] > 0) {
      bg = '#22c55e';
    } else {
      bg = 'var(--border)';
    }
    const marker = isToday ? '<div class="timeline-today-marker"></div>' : '';
    daysHtml += `<div class="timeline-day" style="height:${hPct}%;background:${bg}" title="${i + 1}: ${dayDeadlines[i]} дедлайнов">${marker}</div>`;
    labelsHtml += `<span class="timeline-label${isToday ? ' today' : ''}"${isWeekend ? ' style="opacity:0.4"' : ''}>${i + 1}</span>`;
  }
  tlDiv.innerHTML = `<div class="timeline-title">Дедлайны в ${MONTHS_FULL[curMonth].toLowerCase()} ${curYear}</div>
    <div class="timeline-track">${daysHtml}</div>
    <div class="timeline-labels">${labelsHtml}</div>
    <div class="timeline-legend">
      <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:var(--danger)"></span> Просрочено</span>
      <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:#f59e0b"></span> Скоро</span>
      <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:#22c55e"></span> В срок</span>
      <span class="timeline-leg-item"><span class="timeline-leg-dot" style="background:var(--muted);opacity:0.3"></span> Выходной</span>
      ${isCurrentMonth ? '<span class="timeline-leg-item" style="color:var(--accent);font-weight:600">▼ Сегодня</span>' : ''}
    </div>`;
  viz.appendChild(tlDiv);

  // ── Аккордеон секций ─────────────────────────────────────────────────────
  const sections = [
    {
      icon: '🔴',
      cls: 'danger',
      title: `Просроченные работы (всего ${overdue.length})`,
      count: overdue.length,
      items: overdue.map((t) => {
        const de = t.date_end ? t.date_end.slice(0, 10) : null;
        const dead = t.deadline ? t.deadline.slice(0, 10) : null;
        const daysCalc = de
          ? Math.floor((new Date(todayStr) - new Date(de)) / 86400000)
          : dead
            ? Math.floor((new Date(todayStr) - new Date(dead)) / 86400000)
            : 0;
        return {
          title: t.work_name || `Работа #${t.id}`,
          meta: `${t.task_type || ''} · ${t.executor || '—'} · Окончание: ${de || '—'} · Срок: ${dead || '—'}`,
          highlight: `Просрочено на ${daysCalc} дн.`,
          actions: [
            {
              label: '✏️ Редактировать',
              fn: () => {
                closePeModal();
                openEditTaskModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
            {
              label: '📝 Внести отчёт',
              fn: () => {
                closePeModal();
                openReportModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
            {
              label: 'Игнорировать',
              fn: () => {
                peSetIgnored('overdue_' + t.id);
                closePeModal();
              },
            },
          ],
        };
      }),
    },
    {
      icon: '🟣',
      cls: 'debt',
      title: `Долги — незакрытые работы из прошлых периодов (${debts.length})`,
      count: debts.length,
      items: debts.map((t) => {
        const de = t.date_end ? t.date_end.slice(0, 10) : null;
        const dead = t.deadline ? t.deadline.slice(0, 10) : null;
        const daysCalc = de
          ? Math.floor((new Date(todayStr) - new Date(de)) / 86400000)
          : dead
            ? Math.floor((new Date(todayStr) - new Date(dead)) / 86400000)
            : 0;
        return {
          title: t.work_name || `Работа #${t.id}`,
          meta: `${t.task_type || ''} · ${t.executor || '—'} · Окончание: ${de || '—'} · Срок: ${dead || '—'}`,
          highlight: `Долг ${daysCalc} дн.`,
          actions: [
            {
              label: '✏️ Редактировать',
              fn: () => {
                closePeModal();
                openEditTaskModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
            {
              label: '📝 Внести отчёт',
              fn: () => {
                closePeModal();
                openReportModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
            {
              label: 'Игнорировать',
              fn: () => {
                peSetIgnored('debt_' + t.id);
                closePeModal();
              },
            },
          ],
        };
      }),
    },
    {
      icon: '🟠',
      cls: 'warn',
      title: `Ошибки в датах (всего ${badDates.length})`,
      count: badDates.length,
      items: badDates.map((t) => ({
        title: t.work_name || `Работа #${t.id}`,
        meta: `${t.executor || '—'} · Начало: ${(t.date_start || '').slice(0, 10) || '—'} · Окончание: ${(t.date_end || '').slice(0, 10) || '—'}`,
        highlight: 'Дата начала позже даты окончания/срока',
        actions: [
          {
            label: '✏️ Исправить',
            fn: () => {
              closePeModal();
              openEditTaskModal(tasks.find((x) => x.id === t.id) || { id: t.id });
            },
          },
          {
            label: 'Игнорировать',
            fn: () => {
              peSetIgnored('baddates_' + t.id);
              closePeModal();
            },
          },
        ],
      })),
    },
    {
      icon: '🔴',
      cls: 'danger',
      title: `Перегруженные (всего ${overloaded.length}, >${Math.round(monthNorm * 1.1)} ч)`,
      count: overloaded.length,
      items: overloaded.map((e) => ({
        title: e.name,
        meta: `Загрузка: ${e.hours.toFixed(1)} ч · Норма: ${monthNorm} ч`,
        highlight: `Перегруз: +${(e.hours - monthNorm).toFixed(1)} ч`,
        actions: [
          {
            label: '🔍 Показать работы',
            fn: () => {
              closePeModal();
              filterByExecutorCurMonth(e.name, curYear, curMonth);
            },
          },
          {
            label: 'Оставить как есть',
            fn: () => {
              peSetIgnored('overload_' + e.name + '_' + curKey);
              closePeModal();
            },
          },
        ],
      })),
    },
    {
      icon: '🟡',
      cls: 'warn',
      title: `Недозагруженные (всего ${underloaded.length}, норма ${monthNorm} ч)`,
      count: underloaded.length,
      items: underloaded.map((e) => ({
        title: e.name,
        meta: `Загрузка: ${e.hours.toFixed(1)} ч · Норма: ${e.norm || monthNorm} ч`,
        highlight: `Дефицит: ${((e.norm || monthNorm) - e.hours).toFixed(1)} ч`,
        actions: [
          {
            label: '🔍 Показать работы',
            fn: () => {
              closePeModal();
              filterByExecutorCurMonth(e.name, curYear, curMonth);
            },
          },
          {
            label: 'Оставить как есть',
            fn: () => {
              peSetIgnored('underload_' + e.name + '_' + curKey);
              closePeModal();
            },
          },
        ],
      })),
    },
    {
      icon: '⏰',
      cls: 'warn',
      title: `Истекает срок в ближайшие 7 дней (${soonExpiring.length})`,
      count: soonExpiring.length,
      id: 'peSoonExpiring',
      items: soonExpiring.map((t) => {
        const de = t.date_end ? t.date_end.slice(0, 10) : null;
        const dead = t.deadline ? t.deadline.slice(0, 10) : null;
        const endDate = de || dead || '—';
        const daysLeft = de
          ? Math.ceil((new Date(de) - new Date(todayStr)) / 86400000)
          : dead
            ? Math.ceil((new Date(dead) - new Date(todayStr)) / 86400000)
            : 0;
        const daysText =
          daysLeft === 0 ? 'сегодня' : daysLeft === 1 ? 'завтра' : `через ${daysLeft} дн.`;
        return {
          title: t.work_name || `Работа #${t.id}`,
          meta: `${t.task_type || ''} · ${t.executor || 'нет исполнителя'} · Окончание: ${endDate}`,
          highlight:
            daysLeft <= 1 ? 'Срок истекает ' + daysText + '!' : 'Осталось ' + daysLeft + ' дн.',
          actions: [
            {
              label: '✏️ Редактировать',
              fn: () => {
                closePeModal();
                openEditTaskModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
            {
              label: '📝 Внести отчёт',
              fn: () => {
                closePeModal();
                openReportModal(tasks.find((x) => x.id === t.id) || { id: t.id });
              },
            },
          ],
        };
      }),
    },
    {
      icon: '📅',
      cls: 'warn',
      title: `Конфликт с отпуском (всего ${vacConflicts.length})`,
      count: vacConflicts.length,
      items: vacConflicts.map((v) => {
        const name = v.executor || v.executor_name || '—';
        return {
          title: name,
          meta: `Отпуск: ${v.date_start || '—'} — ${v.date_end || '—'} · ${v.vac_type || ''}`,
          highlight: 'Задачи в период отпуска',
          actions: [
            {
              label: 'Игнорировать',
              fn: () => {
                peSetIgnored(v.ignKey);
                closePeModal();
              },
            },
            {
              label: '✏️ Скорректировать план',
              fn: () => {
                closePeModal();
                filterByExecutorCurMonth(name, curYear, curMonth);
              },
            },
            {
              label: '📅 Скорректировать отпуск',
              fn: () => {
                closePeModal();
                window.location.href = '/employees/vacation-plan/';
              },
            },
          ],
        };
      }),
    },
  ];

  sections.forEach((s) => body.appendChild(buildPeSection(s)));

  // Секции всегда свёрнуты — пользователь сам развернёт нужные
}

function escapePe(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function buildPeSection({ icon, cls, title, count, items, id }) {
  const sec = document.createElement('div');
  sec.className = 'va-section';
  if (id) sec.id = id;
  const badgeCls = count > 0 ? cls : 'ok';
  const iconCls = count > 0 ? cls : 'ok';

  const secBody = document.createElement('div');
  secBody.className = 'va-sec-body';

  const hdr = document.createElement('div');
  hdr.className = 'va-sec-hdr';
  hdr.innerHTML = `<div class="va-sec-icon ${iconCls}">${count > 0 ? icon : '✓'}</div>
    <div class="va-sec-title">${escapePe(title)}</div>
    <span class="va-sec-count ${badgeCls}">${count}</span>
    <span class="va-sec-arrow">▼</span>`;
  hdr.onclick = () => {
    secBody.classList.toggle('open');
    hdr.querySelector('.va-sec-arrow').textContent = secBody.classList.contains('open') ? '▲' : '▼';
  };

  items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'pe-item';
    row.innerHTML = `<div class="pe-item-info">
        <div class="pe-item-name">${escapePe(item.title)}</div>
        <div class="pe-item-meta">${escapePe(item.meta)} · <span>${escapePe(item.highlight)}</span></div>
        <div class="pe-item-actions"></div>
      </div>`;
    const ac = row.querySelector('.pe-item-actions');
    item.actions.forEach((a) => {
      const btn = document.createElement('button');
      btn.className = 'pe-btn';
      btn.textContent = a.label;
      btn.addEventListener('click', a.fn);
      ac.appendChild(btn);
    });
    secBody.appendChild(row);
  });

  if (items.length === 0) {
    secBody.innerHTML =
      '<div style="padding:14px 24px;font-size:16px;color:var(--muted)">✓ Ошибок не найдено</div>';
  }

  sec.appendChild(hdr);
  sec.appendChild(secBody);
  return sec;
}

function closePeModal() {
  document.getElementById('peModal').classList.remove('open');
}

function filterByExecutor(name) {
  clearAllColFilters();
  const sel = new Set([name]);
  mfSelections['executor'] = sel;
  colFilters['mf_executor'] = sel;
  document.querySelectorAll(".mf-trigger[data-col='executor']").forEach((btn) => {
    if (!btn.classList.contains('mf-icon')) btn.textContent = name;
    btn.classList.add('active');
  });
  document.getElementById('filtersActiveBadge').classList.add('visible');
  renderTable();
}

async function filterByExecutorCurMonth(name, year, month) {
  // Переключаем период на текущий календарный месяц
  if (selectedYear !== year || selectedMonth !== month) {
    selectedYear = year;
    selectedMonth = month;
    showAll = false;
    localStorage.setItem('plan_year', selectedYear);
    localStorage.setItem('plan_month', selectedMonth);
    document.getElementById('yearDisplay').textContent = selectedYear;
    document.querySelectorAll('.cal-month').forEach((el) => {
      el.classList.toggle('active', parseInt(el.dataset.m) === selectedMonth);
    });
    await loadTasks();
  }
  // Применяем фильтр по исполнителю
  filterByExecutor(name);
}

// ══════════════════════════════════════════════════════════════════════════
// MONTH-START CHECK
// ══════════════════════════════════════════════════════════════════════════
const MCC_KEY = 'mcc_last_checked';

async function checkMonthStart() {
  const now = new Date();
  const todayKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const lastChecked = localStorage.getItem(MCC_KEY);
  if (now.getDate() !== 1 || lastChecked === todayKey) return;

  const prevMonth = now.getMonth() === 0 ? 12 : now.getMonth();
  const prevYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();

  let monthTasks;
  try {
    const res = await fetch(`/api/tasks/?year=${prevYear}&month=${prevMonth}`);
    monthTasks = res.ok ? await res.json() : [];
  } catch (e) {
    console.error('checkMonthStart: fetch error', e);
    return;
  }
  if (!monthTasks.length) {
    localStorage.setItem(MCC_KEY, todayKey);
    return;
  }

  // has_reports приходит из API задач — N+1 fetch не нужен
  const missing = monthTasks.filter((t) => !t.has_reports);
  if (!missing.length) {
    localStorage.setItem(MCC_KEY, todayKey);
    return;
  }
  openMonthCheckModal(missing, prevYear, prevMonth, todayKey);
}

const mccDecisions = {};
let mccTodayKey = '';

function openMonthCheckModal(tasksList, year, month, todayKey) {
  Object.keys(mccDecisions).forEach((k) => delete mccDecisions[k]);
  mccTodayKey = todayKey;
  // MONTHS_FULL — в utils.js
  document.getElementById('monthCheckSub').textContent =
    `${MONTHS_FULL[month]} ${year} — ${tasksList.length} работ без отчёта`;

  const body = document.getElementById('monthCheckBody');
  body.innerHTML = '';

  tasksList.forEach((t) => {
    const block = document.createElement('div');
    block.className = 'mcc-task';
    block.id = `mcc-task-${t.id}`;
    const execStr = t.executor ? ` · ${t.executor}` : '';
    const deptStr = t.dept ? ` · ${t.dept}` : '';
    block.innerHTML = `
      <div class="mcc-task-name">${t.work_name || `Работа #${t.id}`}</div>
      <div class="mcc-task-meta">${t.task_type || ''}${deptStr}${execStr} · ${t.date_start || '—'} → ${t.date_end || '—'}</div>
      <div class="mcc-actions">
        <button class="mcc-btn" onclick="mccTogglePostpone(${t.id})">📅 Перенести на следующий месяц</button>
        <button class="mcc-btn danger" onclick="mccFinish(${t.id}, this)">✓ Завершить работу</button>
        <button class="mcc-btn primary" onclick="mccOpenReport(${t.id}, '${escapeJs(t.work_name || '')}')">📝 Внести отчёт</button>
      </div>
      <div class="mcc-postpone-form" id="mcc-pform-${t.id}">
        <div class="mcc-form-row">
          <div class="mcc-form-field">
            <label>Новая дата начала</label>
            <input type="date" id="mcc-ds-${t.id}" value="${t.date_start || ''}">
          </div>
          <div class="mcc-form-field">
            <label>Новая дата окончания</label>
            <input type="date" id="mcc-de-${t.id}" value="">
          </div>
          <div class="mcc-form-field">
            <label>Срок выполнения</label>
            <input type="date" id="mcc-dead-${t.id}" value="${t.deadline || ''}">
          </div>
          <div class="mcc-form-field" style="min-width:140px">
            <label>Исполнитель</label>
            <select id="mcc-exec-${t.id}"></select>
          </div>
          <div class="mcc-form-field">
            <label>План (ч) след. месяц</label>
            <input type="number" id="mcc-hours-${t.id}" value="" placeholder="0" style="width:80px">
          </div>
        </div>
        <button class="mcc-btn primary" onclick="mccConfirmPostpone(${t.id})">✓ Подтвердить перенос</button>
      </div>`;

    const sel = block.querySelector(`#mcc-exec-${t.id}`);
    (dirs['_ids_employees'] || []).forEach((e) => {
      const o = document.createElement('option');
      o.value = e.value;
      o.textContent = e.value;
      if (e.value === t.executor) o.selected = true;
      sel.appendChild(o);
    });
    body.appendChild(block);
  });

  mccUpdateProgress(tasksList.length);
  document.getElementById('monthCheckModal').classList.add('open');
}

function closeMonthCheckModal() {
  document.getElementById('monthCheckModal').classList.remove('open');
  if (mccTodayKey) localStorage.setItem(MCC_KEY, mccTodayKey);
}
function mccUpdateProgress(total) {
  const done = Object.keys(mccDecisions).length;
  document.getElementById('mccProgress').textContent = `Обработано: ${done} из ${total}`;
}
function mccTogglePostpone(taskId) {
  document.getElementById(`mcc-pform-${taskId}`).classList.toggle('open');
}
function mccFinish(taskId, btn) {
  mccDecisions[taskId] = { action: 'finish' };
  const block = document.getElementById(`mcc-task-${taskId}`);
  block.querySelectorAll('.mcc-btn').forEach((b) => b.classList.remove('done'));
  btn.classList.add('done');
  btn.textContent = '✓ Будет завершена';
  mccUpdateProgress(document.querySelectorAll('.mcc-task').length);
}
function mccConfirmPostpone(taskId) {
  const ds = document.getElementById(`mcc-ds-${taskId}`).value;
  const de = document.getElementById(`mcc-de-${taskId}`).value;
  const dead = document.getElementById(`mcc-dead-${taskId}`).value;
  const exec = document.getElementById(`mcc-exec-${taskId}`).value;
  const hrs = parseFloat(document.getElementById(`mcc-hours-${taskId}`).value) || 0;
  if (!de) {
    notify('Укажите новую дату окончания', 'err');
    return;
  }
  mccDecisions[taskId] = { action: 'postpone', ds, de, dead, executor: exec, hours: hrs };
  const block = document.getElementById(`mcc-task-${taskId}`);
  document.getElementById(`mcc-pform-${taskId}`).classList.remove('open');
  const postponeBtn = block.querySelector('.mcc-btn');
  postponeBtn.textContent = `📅 Перенос → ${de}`;
  postponeBtn.classList.add('done');
  mccUpdateProgress(document.querySelectorAll('.mcc-task').length);
}
function mccOpenReport(taskId, taskName) {
  closeMonthCheckModal();
  const taskObj = tasks.find((x) => x.id === taskId) || { id: taskId, work_name: taskName };
  openReportModal(taskObj);
  const origClose = window._origCloseReport || closeReportModal;
  window._origCloseReport = closeReportModal;
  window.closeReportModal = function () {
    origClose();
    mccDecisions[taskId] = { action: 'reported' };
    document.getElementById('monthCheckModal').classList.add('open');
    window.closeReportModal = origClose;
    mccUpdateProgress(document.querySelectorAll('.mcc-task').length);
    const block = document.getElementById(`mcc-task-${taskId}`);
    if (block) {
      const btn = block.querySelector('.mcc-btn.primary');
      if (btn) {
        btn.textContent = '✓ Отчёт внесён';
        btn.classList.add('done');
      }
    }
  };
}
async function mccDoneAll() {
  let processed = 0;
  for (const [taskId, decision] of Object.entries(mccDecisions)) {
    const id = parseInt(taskId);
    if (decision.action === 'finish') {
      const res = await fetch(`/api/tasks/${id}/`, {
        method: 'PUT',
        headers: apiHeaders(),
        body: JSON.stringify({ _mcc_finish: true }),
      });
      if (res.ok) processed++;
    } else if (decision.action === 'postpone') {
      const ph = {};
      if (decision.hours > 0 && decision.de) {
        const de = new Date(decision.de);
        const key = `${de.getFullYear()}-${String(de.getMonth() + 1).padStart(2, '0')}`;
        ph[key] = decision.hours;
      }
      const res = await fetch(`/api/tasks/${id}/`, {
        method: 'PUT',
        headers: apiHeaders(),
        body: JSON.stringify({
          date_start: decision.ds || null,
          date_end: decision.de,
          deadline: decision.dead || null,
          executor: decision.executor || null,
          plan_hours_update: ph,
        }),
      });
      if (res.ok) processed++;
    }
  }
  closeMonthCheckModal();
  if (processed > 0) {
    await loadTasks();
    notify(`✓ Обработано ${processed} работ`, 'ok');
  }
}
async function runMonthCheckIfNeeded() {
  await checkMonthStart();
}

// ── PLAN SUMMARY ──────────────────────────────────────────────────────────

// Форматирование целого числа часов с разделителем тысяч (русская локаль).
function _fmtHours(v) {
  const n = Math.round(parseFloat(v) || 0);
  return n.toLocaleString('ru-RU');
}

function updatePlanSummary() {
  const monthKey = selectedMonth
    ? `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`
    : null;

  // Исполнители считаются локально (для подписи «N сотр.»),
  // часы/норма/загрузка — из снимка месяца (источник правды),
  // либо (если месяц не выбран или снимок не загружен) локальная сумма plan_hours.
  const baseData = _spTasksWithoutStatusFilter();
  const executorSet = new Set();
  let localTotal = 0;
  baseData.forEach((t) => {
    const ph = t.plan_hours_all || {};
    if (monthKey) {
      localTotal += parseFloat(ph[monthKey] || 0);
    } else if (showAll) {
      localTotal += Object.values(ph).reduce((s, v) => s + (parseFloat(v) || 0), 0);
    } else {
      Object.entries(ph).forEach(([k, v]) => {
        if (k.startsWith(String(selectedYear))) localTotal += parseFloat(v) || 0;
      });
    }
    if (t.executor) executorSet.add(t.executor);
    if (t.executors_list) {
      t.executors_list.forEach(function (ex) {
        if (ex.name) executorSet.add(ex.name);
      });
    }
  });

  // ── Бейдж: «факт / норма» с разбивкой ──
  // Когда месяц выбран и снимок загружен — берём готовые числа (план, долг, норма).
  // Иначе показываем просто локальную сумму часов (без нормы и долга).
  const ratioEl = document.getElementById('planSummaryValue');
  const useSnap = !!(monthKey && _snapHours && _snapLastMonth === monthKey);
  if (useSnap) {
    const plan = parseFloat(_snapHours.planned || 0);
    const debt = parseFloat(_snapHours.debt || 0);
    const total = parseFloat(_snapHours.total || plan + debt);
    const norm = parseFloat(_snapHours.norm || 0);
    let html = '<span class="sbr-num"><i class="fas fa-clock"></i>' + _fmtHours(total) + '</span>';
    if (norm > 0) {
      html +=
        '<span class="sbr-slash">/</span>' +
        '<span class="sbr-norm">' +
        _fmtHours(norm) +
        ' ч</span>';
    } else {
      html += '<span class="sbr-slash">ч</span>';
    }
    const parts = [];
    if (plan > 0) parts.push('<span class="p">' + _fmtHours(plan) + ' план</span>');
    if (debt > 0) parts.push('<span class="d">' + _fmtHours(debt) + ' долг</span>');
    if (parts.length > 0) {
      html += '<span class="sbr-break">' + parts.join('<span class="sep">·</span>') + '</span>';
    }
    ratioEl.innerHTML = html;
  } else {
    ratioEl.innerHTML =
      '<span class="sbr-num"><i class="fas fa-clock"></i>' +
      _fmtHours(localTotal) +
      '</span><span class="sbr-slash">ч</span>';
  }

  // ── Бейдж: период ──
  let periodLabel;
  if (monthKey) {
    periodLabel = `${MONTHS_SHORT[selectedMonth]} ${selectedYear}`;
  } else if (showAll) {
    periodLabel = 'Все периоды';
  } else {
    periodLabel = `Год ${selectedYear}`;
  }
  const filtered = _spFiltered.length;
  document.getElementById('planSummaryPeriod').innerHTML =
    '<i class="fas fa-calendar"></i> ' + periodLabel + ' · ' + filtered + ' задач';

  // ── Бейдж: сотрудники ──
  const staffCount = executorSet.size;
  document.getElementById('planSummaryStaff').innerHTML =
    '<i class="fas fa-users"></i> ' + (staffCount > 0 ? staffCount + ' сотр.' : '—');

  // ── Бейдж: отдел ──
  const deptNames = spSelectedDepts.size > 0 ? [...spSelectedDepts].join(', ') : 'Все отделы';
  document.getElementById('planSummaryDept').innerHTML =
    '<i class="fas fa-building"></i> ' + deptNames;

  // ── Сплит-бейдж загрузки: план% / с долгом% ──
  // Когда снимка нет (год/все периоды) — считаем локально, одним числом «план%».
  const loadEl = document.getElementById('planSummaryLoad');
  if (useSnap) {
    const planPct = Math.round(parseFloat(_snapHours.load_plan_pct || 0));
    const totalPct = Math.round(parseFloat(_snapHours.load_total_pct || 0));
    const hasDebt = parseFloat(_snapHours.debt || 0) > 0;
    // Класс: ok — план ≤ 100; warn — план 101..125; (иначе sb-load-split — перегруз)
    let cls = 'stat-badge sb-load-split';
    if (planPct <= 100) cls += ' ok';
    else if (planPct <= 125) cls += ' warn';
    let html =
      '<span class="lsp-part lsp-plan"><i class="fas fa-tachometer-alt"></i>' +
      planPct +
      '%</span>';
    if (hasDebt) {
      html +=
        '<span class="lsp-sep">/</span>' +
        '<span class="lsp-part lsp-total">' +
        totalPct +
        '%</span>';
    }
    loadEl.className = cls;
    loadEl.innerHTML = html;
  } else {
    // Фолбэк: локальный расчёт по _spCalCache (год целиком или показать —)
    const calYear = selectedYear || new Date().getFullYear();
    const calArr = _spCalCache[calYear] || [];
    let capacity = 0;
    if (staffCount > 0 && calArr.length > 0) {
      if (monthKey && selectedMonth) {
        const ce = calArr.find((c) => c.month === selectedMonth);
        capacity = staffCount * (ce ? ce.hours_norm : 160);
      } else {
        const yearNorm = calArr.reduce((s, c) => s + (c.hours_norm || 0), 0);
        capacity = staffCount * yearNorm;
      }
    }
    loadEl.className = 'stat-badge sb-load-split';
    if (capacity > 0) {
      const pct = Math.round((localTotal / capacity) * 100);
      if (pct <= 100) loadEl.className = 'stat-badge sb-load-split ok';
      else if (pct <= 125) loadEl.className = 'stat-badge sb-load-split warn';
      loadEl.innerHTML =
        '<span class="lsp-part lsp-plan"><i class="fas fa-tachometer-alt"></i>' + pct + '%</span>';
    } else {
      loadEl.innerHTML =
        '<span class="lsp-part lsp-plan"><i class="fas fa-tachometer-alt"></i>—</span>';
    }
  }
}

// ── Форматирование YYYY-MM → «Март 2026» ─────────────────────────────────
const _SP_MONTH_NAMES = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];
function _spFormatYearMonth(ym) {
  const [y, m] = ym.split('-');
  const mi = parseInt(m, 10) - 1;
  return (_SP_MONTH_NAMES[mi] || m) + ' ' + y;
}

// ── MULTI-SELECT FILTER ───────────────────────────────────────────────────
const mfSelections = {};
let activeMfBtn = null;
let activeMfDropdown = null;
const MF_DEFAULTS = {
  dept: '▼',
  sector: '▼',
  project: '▼',
  stage: '▼',
  executor: '▼',
  task_type: '▼',
  work_order: '▼',
  work_number: '▼',
  justification: '▼',
  description: '▼',
  work_name: '▼',
  date_start: '▼',
  date_end: '▼',
};

function getMfValues(col) {
  const vals = new Set();
  // Для сектора — показываем только секторы выбранного отдела
  const deptFilter = col === 'sector' ? mfSelections['dept'] || new Set() : null;
  tasks.forEach((t) => {
    if (deptFilter && deptFilter.size > 0 && !deptFilter.has(t.dept)) return;
    if (col === 'executor') {
      if (t.executor) vals.add(t.executor);
      (t.executors_list || []).forEach((ex) => {
        if (ex.name) vals.add(ex.name);
      });
    } else if (col === 'has_deps') {
      vals.add((t.predecessors_count || 0) > 0 ? 'Со связями' : 'Без связей');
    } else if (col === 'task_type') {
      vals.add(t.task_type || 'ПП');
    } else if (col === 'date_start' || col === 'date_end') {
      // Даты группируем по году-месяцу (YYYY-MM)
      if (t[col] && t[col].length >= 7) vals.add(t[col].slice(0, 7));
    } else {
      if (t[col]) vals.add(t[col]);
    }
  });
  return [...vals].sort((a, b) => a.localeCompare(b, 'ru'));
}

function buildMfDropdown(btn, col) {
  if (activeMfDropdown) activeMfDropdown.remove();
  const vals = getMfValues(col);
  const selected = mfSelections[col] || new Set();
  const drop = document.createElement('div');
  drop.className = 'mf-dropdown open';
  drop.dataset.col = col;

  const searchWrap = document.createElement('div');
  searchWrap.className = 'mf-search';
  const searchInp = document.createElement('input');
  searchInp.placeholder = 'Поиск...';
  searchInp.autocomplete = 'off';
  const _isDateCol = col === 'date_start' || col === 'date_end';
  searchInp.oninput = () => {
    const q = searchInp.value.toLowerCase();
    drop.querySelectorAll('.mf-option').forEach((opt) => {
      const rawVal = opt.dataset.val.toLowerCase();
      const dispVal = (opt.textContent || '').toLowerCase();
      opt.style.display = rawVal.includes(q) || dispVal.includes(q) ? '' : 'none';
    });
  };
  searchWrap.appendChild(searchInp);
  drop.appendChild(searchWrap);

  const actions = document.createElement('div');
  actions.className = 'mf-actions';
  const selectAll = document.createElement('button');
  selectAll.className = 'mf-btn';
  selectAll.textContent = 'Выбрать все';
  selectAll.onclick = (e) => {
    e.stopPropagation();
    const sel = new Set(vals);
    mfSelections[col] = sel;
    drop.querySelectorAll('.mf-option input').forEach((cb) => (cb.checked = true));
    applyMfFilter(col, btn);
  };
  const clearBtn = document.createElement('button');
  clearBtn.className = 'mf-btn';
  clearBtn.textContent = 'Сбросить';
  clearBtn.onclick = (e) => {
    e.stopPropagation();
    mfSelections[col] = new Set();
    drop.querySelectorAll('.mf-option input').forEach((cb) => (cb.checked = false));
    applyMfFilter(col, btn);
  };
  actions.appendChild(selectAll);
  actions.appendChild(clearBtn);
  drop.appendChild(actions);

  vals.forEach((val) => {
    const opt = document.createElement('div');
    opt.className = 'mf-option';
    opt.dataset.val = val;
    opt.tabIndex = 0;
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = selected.has(val);
    cb.tabIndex = -1;
    const toggle = () => {
      cb.checked = !cb.checked;
      const sel = mfSelections[col] || new Set();
      if (cb.checked) sel.add(val);
      else sel.delete(val);
      mfSelections[col] = sel;
      applyMfFilter(col, btn);
    };
    cb.onchange = () => {
      const sel = mfSelections[col] || new Set();
      if (cb.checked) sel.add(val);
      else sel.delete(val);
      mfSelections[col] = sel;
      applyMfFilter(col, btn);
    };
    opt.onclick = (e) => {
      if (e.target !== cb) toggle();
    };
    opt.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle();
      }
    };
    opt.appendChild(cb);
    // Для дат — показываем «Март 2026», для остальных — как есть
    const displayText = _isDateCol ? _spFormatYearMonth(val) : val;
    opt.appendChild(document.createTextNode(displayText));
    drop.appendChild(opt);
  });

  document.body.appendChild(drop);
  const rect = btn.getBoundingClientRect();
  const dropH = drop.offsetHeight || 300;
  const spaceBelow = window.innerHeight - rect.bottom;
  const spaceAbove = rect.top;
  if (spaceBelow < dropH && spaceAbove > spaceBelow) {
    drop.style.top = rect.top + window.scrollY - dropH - 2 + 'px';
  } else {
    drop.style.top = rect.bottom + window.scrollY + 2 + 'px';
  }
  drop.style.left = Math.min(rect.left, window.innerWidth - 250) + 'px';
  activeMfDropdown = drop;
  activeMfBtn = btn;
  setTimeout(() => searchInp.focus(), 50);
}

function toggleMf(btn) {
  if (activeMfDropdown && activeMfBtn === btn) {
    activeMfDropdown.remove();
    activeMfDropdown = null;
    activeMfBtn = null;
    return;
  }
  buildMfDropdown(btn, btn.dataset.col);
}

function applyMfFilter(col, btn) {
  const sel = mfSelections[col] || new Set();
  const isIcon = btn.classList.contains('mf-icon');
  const def = MF_DEFAULTS[col] || '▼';
  if (sel.size === 0) {
    delete colFilters['mf_' + col];
    if (!isIcon) btn.textContent = def;
    btn.classList.remove('active');
  } else {
    colFilters['mf_' + col] = sel;
    if (!isIcon) btn.textContent = sel.size === 1 ? [...sel][0] : `${sel.size} выбрано`;
    btn.classList.add('active');
  }
  // Синхронизация dept-чипов при изменении мультифильтра dept
  if (col === 'dept') {
    spSelectedDepts = new Set(sel);
    _saveSPDepts();
    if (_spDeptFilter) _spDeptFilter.refresh();
    // Сбрасываем фильтр секторов при смене отдела
    if (mfSelections['sector'] && mfSelections['sector'].size > 0) {
      mfSelections['sector'] = new Set();
      delete colFilters['mf_sector'];
      const sectorBtn = document.querySelector('.mf-trigger[data-col="sector"]');
      if (sectorBtn) {
        if (!sectorBtn.classList.contains('mf-icon'))
          sectorBtn.textContent = MF_DEFAULTS['sector'] || '▼';
        sectorBtn.classList.remove('active');
      }
    }
  }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').classList.toggle('visible', hasFilters);
  renderTable();
}

document.addEventListener(
  'click',
  (e) => {
    if (activeMfDropdown && !activeMfDropdown.contains(e.target) && e.target !== activeMfBtn) {
      activeMfDropdown.remove();
      activeMfDropdown = null;
      activeMfBtn = null;
    }
  },
  true,
);

function initMfTriggers() {
  document.querySelectorAll('.mf-trigger').forEach((btn) => {
    const col = btn.dataset.col;
    const sel = mfSelections[col];
    if (!sel || sel.size === 0) {
      if (!btn.classList.contains('mf-icon')) btn.textContent = MF_DEFAULTS[col] || '▼';
      btn.classList.remove('active');
    }
  });
}

// ── FILTER MODE TOGGLE ────────────────────────────────────────────────────
function toggleFilterMode(cb) {
  const instant = cb.checked;
  localStorage.setItem('filterInstant', instant ? '1' : '0');
  document.querySelectorAll('.col-filter').forEach((inp) => {
    if (instant) {
      inp.oninput = debounce(() => applyColFilters(inp), 150);
      inp.onkeydown = null;
    } else {
      inp.oninput = null;
      inp.onkeydown = (e) => {
        if (e.key === 'Enter') applyColFilters(inp);
      };
    }
  });
}
function initFilterMode() {
  const instant = localStorage.getItem('filterInstant') === '1';
  const cb = document.getElementById('filterInstant');
  if (cb) {
    cb.checked = instant;
    toggleFilterMode(cb);
  }
}

// ── COLUMN SORT ───────────────────────────────────────────────────────────
var _spSortState = { col: null, dir: 'asc' };
var _spPinnedRowId = null; // id новой строки, закреплённой сверху
var _spPinKeep = false; // true = пропустить сброс пина при ближайшем loadTasks

function _spInitSort() {
  var thead = document.querySelector('#mainTable thead');
  if (!thead) return;
  thead.querySelectorAll('th[data-sort]').forEach(function (th) {
    th.style.cursor = 'pointer';
    th.style.userSelect = 'none';
    th.addEventListener('click', function (e) {
      // Не сортируем если кликнули на resize-handle или mf-trigger/mf-icon
      if (
        e.target.classList.contains('col-resize') ||
        e.target.classList.contains('mf-trigger') ||
        e.target.closest('.mf-trigger')
      )
        return;
      toggleSort(_spSortState, th.getAttribute('data-sort'));
      renderSortIndicators(thead, _spSortState);
      renderTable();
    });
  });
  renderSortIndicators(thead, _spSortState);
}

// ── COLUMN FILTERS ────────────────────────────────────────────────────────
let colFilters = {};

function applyColFilters(inp) {
  const col = inp.dataset.col;
  const val = inp.value.trim();
  const clearBtn = inp.nextElementSibling;
  if (val) {
    colFilters[col] = val.toLowerCase();
    inp.classList.add('active');
    clearBtn.classList.add('visible');
  } else {
    delete colFilters[col];
    inp.classList.remove('active');
    clearBtn.classList.remove('visible');
  }
  const hasFilters = Object.keys(colFilters).length > 0;
  document.getElementById('filtersActiveBadge').classList.toggle('visible', hasFilters);
  renderTable();
}
function clearColFilter(btn) {
  const inp = btn.previousElementSibling;
  inp.value = '';
  applyColFilters(inp);
}
function clearAllColFilters() {
  colFilters = {};
  document.querySelectorAll('.col-filter').forEach((inp) => {
    inp.value = '';
    inp.classList.remove('active');
    inp.nextElementSibling.classList.remove('visible');
  });
  Object.keys(mfSelections).forEach((k) => (mfSelections[k] = new Set()));
  document.querySelectorAll('.mf-trigger').forEach((btn) => {
    if (!btn.classList.contains('mf-icon')) btn.textContent = MF_DEFAULTS[btn.dataset.col] || '▼';
    btn.classList.remove('active');
  });
  if (activeMfDropdown) {
    activeMfDropdown.remove();
    activeMfDropdown = null;
    activeMfBtn = null;
  }
  document.getElementById('filtersActiveBadge').classList.remove('visible');
  // Сброс dept-фильтра
  spSelectedDepts = new Set();
  _saveSPDepts();
  if (_spDeptFilter) _spDeptFilter.refresh();
  renderTable();
}

// Авторесайз всех textarea в контейнере (подгоняет высоту под содержимое)
function _resizeTextareas(container) {
  var textareas = [].slice.call(container.querySelectorAll('textarea.cell-edit'));
  textareas.forEach(function (ta) {
    ta.style.height = 'auto';
  });
  var heights = textareas.map(function (ta) {
    return ta.scrollHeight;
  });
  textareas.forEach(function (ta, i) {
    ta.style.height = heights[i] + 'px';
  });
}

/* ── Infinite scroll: состояние ленивой отрисовки СП ──────────────────── */
const SP_CHUNK = APP_CONFIG.chunkSize;
let _spFiltered = [];
let _spRenderedCount = 0;
let _spScrollDispose = null;

// Рисует основную таблицу задач: фильтрует по colFilters, рендерит порциями при прокрутке
function renderTable() {
  const tbody = document.getElementById('taskBody');
  tbody.innerHTML = '';
  _spRenderedCount = 0;
  if (_spScrollDispose) {
    _spScrollDispose();
    _spScrollDispose = null;
  }

  _spFiltered = tasks.filter((t) => {
    // Drill-down по снимку месяца: единый фильтр по корзинам (чипы = строки снимка)
    if (_snapBucketFilter && _snapBucketOf(t.id) !== _snapBucketFilter) return false;

    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3);
        if (val.size > 0) {
          // Для executor учитываем и executors_list (несколько исполнителей)
          if (field === 'executor') {
            const inSingle = val.has(t.executor || '');
            const inList = (t.executors_list || []).some((ex) => val.has(ex.name || ''));
            if (!inSingle && !inList) return false;
          } else if (field === 'has_deps') {
            const label = (t.predecessors_count || 0) > 0 ? 'Со связями' : 'Без связей';
            if (!val.has(label)) return false;
          } else if (field === 'task_type') {
            if (!val.has(t.task_type || 'ПП')) return false;
          } else if (field === 'date_start' || field === 'date_end') {
            // Даты сравниваем по году-месяцу (YYYY-MM)
            const cellVal = (t[field] || '').slice(0, 7);
            if (!val.has(cellVal)) return false;
          } else {
            if (!val.has(t[field] || '')) return false;
          }
        }
        continue;
      }
      if (col === 'plan_hours_total') {
        const total = Object.values(t.plan_hours_all || {}).reduce(
          (s, v) => s + (parseFloat(v) || 0),
          0,
        );
        const threshold = parseFloat(val);
        if (!isNaN(threshold) && total < threshold) return false;
        continue;
      }
      const cellVal = (t[col] || '').toString().toLowerCase();
      if (!cellVal.includes(val)) return false;
    }
    return true;
  });

  // Сортировка
  if (_spSortState.col) {
    _spFiltered = applySortToArray(_spFiltered, _spSortState, function (t, col) {
      return t[col] || '';
    });
  }

  // Закреплённая строка — всегда первая (pin сверху)
  if (_spPinnedRowId) {
    const pinIdx = _spFiltered.findIndex((t) => t.id === _spPinnedRowId);
    if (pinIdx > 0) {
      const [pinned] = _spFiltered.splice(pinIdx, 1);
      _spFiltered.unshift(pinned);
    }
  }

  // Обновляем панель статусов (считает по задачам с учётом фильтров, но без статус-фильтра)
  spUpdateStatusPanel();

  const shown = _spFiltered.length;
  // «из N» только при поиске/колоночных фильтрах (dept-фильтр — контекст, не доп. фильтр)
  const _searchVal = document.getElementById('searchInput').value.trim();
  const hasExtraFilters = _searchVal || Object.keys(colFilters).some((k) => k !== 'mf_dept');
  const total = hasExtraFilters ? _spTasksWithoutStatusFilter().length : 0;
  document.getElementById('searchCount').textContent = shown
    ? hasExtraFilters && total !== shown
      ? `${shown} из ${total} зап.`
      : `${shown} зап.`
    : '';

  // Пустое состояние: вообще нет задач
  if (tasks.length === 0) {
    tbody.innerHTML = emptyStateHtml({
      icon: 'fas fa-tasks',
      title: 'Нет задач',
      desc: 'Создайте первую задачу для начала работы',
      action: IS_WRITER
        ? '<button class="btn btn-primary btn-sm" onclick="openNewTaskModal(\'task\')"><i class="fas fa-plus"></i> Создать задачу</button>'
        : '',
      colspan: 17,
    });
    updatePlanSummary();
    return;
  }
  // Пустое состояние: нет строк после фильтрации
  if (
    _spFiltered.length === 0 &&
    (hasExtraFilters || _snapBucketFilter || spSelectedDepts.size > 0)
  ) {
    tbody.innerHTML = emptyStateHtml({
      icon: 'fas fa-search',
      title: 'Ничего не найдено',
      desc: 'Попробуйте изменить фильтры или сбросить поиск',
      action:
        '<button class="btn btn-primary btn-sm" onclick="openNewTaskModal(\'task\')"><i class="fas fa-plus"></i> Новая задача</button>',
      colspan: 17,
    });
    updatePlanSummary();
    return;
  }

  // Рендерим первую порцию
  _spAppendBatch(SP_CHUNK);
  // Дополнительный ресайз textarea после layout (гарантия корректных высот)
  requestAnimationFrame(() => {
    _resizeTextareas(tbody);
  });
  updatePlanSummary();
  // Ставим слушатель прокрутки для подгрузки следующих порций
  _spAttachScrollListener();
  // Пересчёт sticky top для строк thead (зависит от режима отображения)
  const _wrap = document.querySelector('.table-wrap');
  if (_wrap) requestAnimationFrame(() => _fixStickyHeaderTops(_wrap));
}

/* ── Добавление порции строк в таблицу СП ─────────────────────────── */
function _spAppendBatch(count) {
  const tbody = document.getElementById('taskBody');
  const end = Math.min(_spRenderedCount + count, _spFiltered.length);
  const spinner = document.getElementById('spScrollSpinner');
  if (spinner) spinner.remove();

  const frag = document.createDocumentFragment();
  for (let i = _spRenderedCount; i < end; i++) {
    frag.appendChild(makeRow(_spFiltered[i], i + 1));
  }
  tbody.appendChild(frag);

  // Запоминаем диапазон ПЕРЕД обновлением _spRenderedCount,
  // иначе rAF-callback увидит _spRenderedCount === end и не обработает строки
  const batchStart = _spRenderedCount;
  _spRenderedCount = end;

  // Авто-высота textarea для новых строк (синхронно — rAF не успевает до следующего renderTable)
  {
    const allRows = tbody.querySelectorAll('tr');
    var textareas = [];
    for (let r = batchStart; r < end && r < allRows.length; r++) {
      allRows[r].querySelectorAll('textarea.cell-edit').forEach((ta) => textareas.push(ta));
    }
    textareas.forEach((ta) => {
      ta.style.height = 'auto';
    });
    var heights = textareas.map((ta) => ta.scrollHeight);
    textareas.forEach((ta, i) => {
      ta.style.height = heights[i] + 'px';
    });
  }

  /* ── Кастомные dropdown-ы для select ──────────────────────────────── */
  if (typeof initCustomDropdowns === 'function') initCustomDropdowns(tbody);

  // Показываем спиннер, если ещё есть строки
  if (_spRenderedCount < _spFiltered.length) {
    const spinnerTr = document.createElement('tr');
    spinnerTr.id = 'spScrollSpinner';
    spinnerTr.innerHTML =
      '<td colspan="15" class="scroll-spinner"><i class="fas fa-spinner"></i> Загружено ' +
      _spRenderedCount +
      ' из ' +
      _spFiltered.length +
      '...</td>';
    tbody.appendChild(spinnerTr);
  }
}

/* ── Слушатель прокрутки для ленивой подгрузки строк СП ───────────── */
function _spAttachScrollListener() {
  if (_spScrollDispose) {
    _spScrollDispose();
    _spScrollDispose = null;
  }
  if (_spRenderedCount >= _spFiltered.length) return;

  _spScrollDispose = createScrollLoader(
    document.querySelector('.table-wrap'),
    () => {
      if (_spRenderedCount < _spFiltered.length) {
        _spAppendBatch(SP_CHUNK);
        if (_spRenderedCount >= _spFiltered.length && _spScrollDispose) {
          _spScrollDispose();
          _spScrollDispose = null;
        }
      }
    },
    200,
  );
}

// ── HELPERS ────────────────────────────────────────────────────────────
function getTaskMonthKeys(dateStart, dateEnd, deadline) {
  const endStr = dateEnd || deadline || null;
  if (!dateStart || !endStr) return [];
  const ds = new Date(dateStart);
  const de = new Date(endStr);
  const keys = [];
  let cur = new Date(ds.getFullYear(), ds.getMonth(), 1);
  const end = new Date(de.getFullYear(), de.getMonth(), 1);
  while (cur <= end) {
    const y = cur.getFullYear();
    const m = String(cur.getMonth() + 1).padStart(2, '0');
    keys.push(`${y}-${m}`);
    cur.setMonth(cur.getMonth() + 1);
  }
  return keys;
}

// ── Создание строки таблицы задач ─────────────────────────────────────────
// Формирует <tr> с ячейками: №, тип, колонки данных, зависимости, действия.
// Для role=user — все поля read-only (текст), для writer — интерактивные.
// Для ПП-записей (isFromPP) — часть полей заблокирована даже для writer.
function makeRow(t, num) {
  // Создаём строку и привязываем ID задачи
  const tr = document.createElement('tr');
  tr.dataset.id = t.id;
  tr.dataset.draggable = 'true';
  // updated_at — для оптимистичной блокировки: клиент возвращает timestamp на PUT,
  // сервер сверяет с БД; при несовпадении — 409
  if (t.updated_at) tr.dataset.updatedAt = t.updated_at;
  // Подсветка строки по статусу.
  // Если снимок месяца активен (выбран ровно один месяц) — используем
  // его корзину как единый источник правды. Иначе — fallback на _spGetStatus
  // (режим «весь год» / «все месяцы»: снимка нет, считаем по has_reports+дедлайну).
  const _snapBucket = _snapBucketOf(t.id);
  if (selectedMonth && !showAll && _snapBucket) {
    // Раскраска строго по корзине снимка
    if (_snapBucket === 'done_early') {
      tr.classList.add('row-early');
    } else if (_snapBucket === 'done' || _snapBucket === 'debt_closed') {
      tr.classList.add('row-done');
    } else if (_snapBucket === 'overdue' || _snapBucket === 'debt_hanging') {
      tr.classList.add('row-overdue');
    } else {
      // inwork
      tr.classList.add('row-inwork');
    }
  } else {
    // Fallback: нет снимка — старая 3-статусная логика
    const _st = _spGetStatus(t);
    if (_st === 'done') tr.classList.add('row-done');
    else if (_st === 'overdue') tr.classList.add('row-overdue');
    else tr.classList.add('row-inwork');
  }
  // Полоса-маркер слева: задача месяца (зелёная) или долг (оранжевая).
  if (_snapBucket === 'debt_closed' || _snapBucket === 'debt_hanging') {
    tr.classList.add('row-debt');
  } else if (_snapBucket) {
    tr.classList.add('row-month');
  }
  // Флаг: задача перенесена из Производственного плана
  const isFromPP = !!t.from_pp;
  if (isFromPP) tr.classList.add('pp-locked');
  // Закреплённая новая строка — зелёная пульсация 9с через CSS box-shadow на TD
  if (t.id === _spPinnedRowId) {
    tr.classList.add('row-pinned');
    setTimeout(function () {
      tr.classList.add('pin-fade');
      setTimeout(function () {
        tr.classList.remove('row-pinned', 'pin-fade');
        _spPinnedRowId = null;
      }, 600);
    }, 9000);
  }

  // ── Колонка «№» с бейджем 🔒 ПП для перенесённых задач ──
  const numTd = document.createElement('td');
  numTd.className = 'num-cell';
  numTd.textContent = num;
  numTd.dataset.label = '№';
  numTd.dataset.colIdx = '0';
  numTd.style.cursor = 'pointer';
  numTd.title = 'Открыть детали задачи';
  numTd.addEventListener('click', function (e) {
    e.stopPropagation();
    openActivityPanel(t.id);
  });
  if (isFromPP) {
    const lockBadge = document.createElement('span');
    lockBadge.className = 'pp-lock-badge';
    lockBadge.dataset.tooltip = 'Перенесено из ПП — редактирование заблокировано';
    lockBadge.textContent = '🔒 пп';
    numTd.appendChild(lockBadge);
  }
  tr.appendChild(numTd);

  // ── Колонка «Код строки» — бейдж типа задачи + row_code ──
  // Код строки (col-idx=2) — вставляется после project
  const rcTd = document.createElement('td');
  rcTd.dataset.label = 'Код строки';
  rcTd.dataset.colIdx = '2';
  rcTd.style.cssText = 'padding:4px 6px;vertical-align:middle;text-align:center;';
  if (t.row_code) {
    const rcSpan = document.createElement('div');
    rcSpan.style.cssText = 'font-family:var(--mono);color:var(--text2);';
    rcSpan.textContent = t.row_code;
    rcTd.appendChild(rcSpan);
  }
  if (t.task_type) {
    const ttWrap = document.createElement('div');
    ttWrap.style.cssText = 'text-align:right;margin-top:2px;';
    ttWrap.innerHTML = taskTypeBadgeHtml(t.task_type, { short: true });
    rcTd.appendChild(ttWrap);
  }

  // Наряд-заказ (col-idx=3) — read-only из ЕТБД
  const woTd = document.createElement('td');
  woTd.dataset.label = 'Наряд-заказ';
  woTd.dataset.colIdx = '3';
  woTd.style.cssText =
    'padding:4px 6px;vertical-align:middle;text-align:center;font-family:var(--mono);color:var(--text2);';
  woTd.textContent = t.work_order || '';
  // rcTd и woTd вставляются ниже, после project

  // ── Определение колонок данных ──
  // Каждая колонка: field — поле в объекте задачи, type — тип ячейки,
  // dirKey — ключ справочника для select, parentField/parentDirKey — каскадная фильтрация,
  // extraField — дополнительное отображение (напр. ФИО руководителя сектора)
  const cols = [
    { field: 'project', type: 'select', dirKey: 'project', readOnly: true, label: 'Проект' },
    {
      field: 'stage',
      type: 'select',
      dirKey: 'stage',
      parentField: 'project',
      parentDirKey: 'project',
      readOnly: true,
      label: '№ Этапа',
    },
    { field: 'work_number', type: 'text', readOnly: true, label: '№ работы' },
    { field: 'justification', type: 'text', label: 'Обоснование' },
    { field: 'description', type: 'text', label: 'Обозначение' },
    { field: 'work_name', type: 'text', label: 'Наименование' },
    { field: 'dept', type: 'select', dirKey: 'dept', label: 'Отдел' },
    {
      field: 'sector',
      type: 'select',
      dirKey: 'sector',
      parentField: 'dept',
      parentDirKey: 'dept',
      extraField: 'sector_head',
      label: 'Сектор',
    },
    { field: 'executor', type: 'select', dirKey: 'executor', label: 'Разработчик' },
    { field: 'date_start', type: 'date', label: 'Начало' },
    { field: 'date_end', type: 'date', label: 'Окончание' },
  ];
  // Сокращённые ключи колонок — для привязки ширин через th-элементы
  const colKeys = [
    'project',
    'stage',
    'wnum',
    'just',
    'desc',
    'wname',
    'dept',
    'sector',
    'exec',
    'spds',
    'spde',
  ];

  // Маппинг индекса в cols → data-col-idx (cols[0]=project→1, cols[1]=stage→4, ...)
  const SP_COL_IDX_MAP = [1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13];

  // ── Цикл по колонкам: создание ячеек данных ──
  cols.forEach((col, idx) => {
    const td = document.createElement('td');
    td.dataset.colIdx = String(SP_COL_IDX_MAP[idx]);
    if (col.label) td.dataset.label = col.label;
    if (col.type === 'date') td.classList.add('td-date');
    // Синхронизируем ширину ячейки с заголовком таблицы
    const thEl = document.getElementById(`th-${colKeys[idx]}`);
    if (thEl && thEl.style.width) td.style.width = thEl.style.width;

    // ── Read-only режим: role=user ИЛИ чужой отдел/сектор ─────────────
    // Все ячейки отображаются как статичный текст без интерактивных элементов.
    // Бэкенд дополнительно защищён WriterRequiredJsonMixin (403 при попытке PUT).
    // Для ПП-записей (isFromPP) не применяем — у них своя логика блокировки.
    if (!IS_WRITER || (!_canModify(t.dept, t.sector) && !isFromPP)) {
      td.style.cssText = 'padding:6px 8px;vertical-align:middle;';
      if (col.field === 'executor') {
        // Исполнители: отображаем как список бейджей (без интерактива)
        const execList = t.executors_list || [];
        if (execList.length > 0) {
          // Обёртка: слева — бейджи исполнителей, справа — суммарная трудоёмкость
          const wrapper = document.createElement('div');
          wrapper.style.cssText = 'display:flex;align-items:center;gap:8px;';
          const container = document.createElement('div');
          container.style.cssText = 'display:flex;flex-direction:column;gap:4px;flex:1;';
          let grandTotal = 0;
          // Каждый исполнитель — фиолетовый бейдж с ФИО и часами
          execList.forEach((ex) => {
            const execItem = document.createElement('div');
            execItem.style.cssText =
              'font-size:15px;color:var(--text);background:rgba(168,85,247,0.1);padding:3px 8px;border-radius:4px;border:1px solid rgba(168,85,247,0.2);';
            const hours = ex.hours || {};
            let totalHours = 0;
            // Если выбран конкретный месяц — показываем часы за месяц, иначе — сумму за все
            if (selectedMonth) {
              const key = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
              totalHours = hours[key] || 0;
            } else {
              totalHours = Object.values(hours).reduce(
                (sum, val) => sum + (parseFloat(val) || 0),
                0,
              );
            }
            grandTotal += totalHours;
            execItem.innerHTML =
              avatarHtml(ex.name, 'sm') +
              ` <strong>${escapeHtml(ex.name)}</strong>${totalHours > 0 ? ` <span style="color:var(--muted);font-family:var(--mono);">(${totalHours}ч)</span>` : ''}`;
            container.appendChild(execItem);
          });
          wrapper.appendChild(container);
          // Суммарная трудоёмкость — синий бейдж справа
          if (grandTotal > 0) {
            const totalEl = document.createElement('div');
            totalEl.style.cssText =
              'min-width:44px;text-align:center;font-family:var(--mono);font-size:15px;font-weight:600;color:var(--accent);background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.2);border-radius:6px;padding:4px 6px;white-space:nowrap;flex-shrink:0;';
            totalEl.textContent = grandTotal + ' ч';
            wrapper.appendChild(totalEl);
          }
          td.appendChild(wrapper);
        } else {
          // Нет исполнителей — аватар + текст поля
          const name = t[col.field] || '';
          if (name) {
            td.innerHTML = avatarHtml(name, 'sm') + ' ' + escapeHtml(name);
          } else {
            td.textContent = '';
          }
        }
      } else if (col.type === 'date') {
        // Даты: преобразуем YYYY-MM-DD → DD.MM.YYYY
        const dateStr = t[col.field] ? t[col.field].split('-').reverse().join('.') : '';
        if (col.field === 'date_end') {
          // Ячейка «Окончание» — дата + бейдж снимка под ней
          td.classList.add('deadline-cell');
          const dateSpan = document.createElement('span');
          dateSpan.className = 'deadline-cell__date';
          dateSpan.textContent = dateStr;
          const badge = document.createElement('span');
          badge.className = 'status-badge';
          badge.dataset.role = 'snap-badge';
          _fillSnapBadge(badge, _snapBucketOf(t.id));
          td.appendChild(dateSpan);
          td.appendChild(badge);
        } else {
          td.textContent = dateStr;
        }
      } else if (col.type === 'select' && col.extraField) {
        // Сектор: код + ФИО начальника серым под ним
        td.textContent = t[col.field] || '';
        const sectorCode = t[col.field] || '';
        const sectorEntry = (dirs['_ids_sector'] || []).find((s) => s.value === sectorCode);
        const headName = sectorEntry ? sectorEntry.head_name || '' : '';
        if (headName) {
          const extra = document.createElement('div');
          extra.style.cssText = 'font-size:11px;color:var(--muted);margin-top:2px;';
          extra.textContent = headName;
          td.appendChild(extra);
        }
      } else {
        // Все остальные поля (dept, project, stage, text-поля) — просто текст
        td.textContent = t[col.field] || '';
      }
      tr.appendChild(td);
      return; // Пропускаем интерактивную часть ниже
    }

    // ── Writer: интерактивные поля ─────────────────────────────────────
    // Для writer — полные select/textarea/input с обработчиками сохранения.

    if (col.field === 'executor') {
      // Колонка «Исполнитель» — особая логика отображения
      td.style.cssText = 'padding:6px 8px;vertical-align:middle;';
      const execList = t.executors_list || [];
      if (execList.length > 0 || isFromPP) {
        // Если есть исполнители — показываем бейджи (не select)
        // Обёртка: слева — список исполнителей, справа — суммарная трудоёмкость
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'display:flex;align-items:center;gap:8px;';

        const container = document.createElement('div');
        container.style.cssText = 'display:flex;flex-direction:column;gap:4px;flex:1;';

        let grandTotal = 0;
        // Каждый исполнитель — фиолетовый бейдж с ФИО и часами за период
        execList.forEach((ex) => {
          const execItem = document.createElement('div');
          execItem.style.cssText =
            'font-size:15px;color:var(--text);background:rgba(168,85,247,0.1);padding:3px 8px;border-radius:4px;border:1px solid rgba(168,85,247,0.2);';
          const hours = ex.hours || {};
          let totalHours = 0;
          // Если выбран конкретный месяц — часы за этот месяц, иначе — сумма за все
          if (selectedMonth) {
            const key = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
            totalHours = hours[key] || 0;
          } else {
            totalHours = Object.values(hours).reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
          }
          grandTotal += totalHours;
          execItem.innerHTML =
            avatarHtml(ex.name, 'sm') +
            ` <strong>${escapeHtml(ex.name)}</strong>${totalHours > 0 ? ` <span style="color:var(--muted);font-family:var(--mono);">(${totalHours}ч)</span>` : ''}`;
          container.appendChild(execItem);
        });

        wrapper.appendChild(container);

        // Суммарная трудоёмкость — синий бейдж справа по центру
        if (grandTotal > 0) {
          const totalEl = document.createElement('div');
          totalEl.style.cssText =
            'min-width:44px;text-align:center;font-family:var(--mono);font-size:15px;font-weight:600;color:var(--accent);background:rgba(59,130,246,0.1);border:1px solid rgba(59,130,246,0.2);border-radius:6px;padding:4px 6px;white-space:nowrap;flex-shrink:0;';
          totalEl.textContent = grandTotal + ' ч';
          wrapper.appendChild(totalEl);
        }

        td.appendChild(wrapper);
      } else {
        // Нет исполнителей — показываем select для выбора (если не ПП)
        const sel = document.createElement('select');
        sel.className = 'cell-select';
        sel.dataset.field = col.field;
        sel.dataset.dirKey = col.dirKey;
        fillSelect(sel, col.dirKey, t[col.field], null, null);
        // При выборе — автосохранение задачи
        sel.addEventListener('change', () => saveTask(t.id, tr));
        td.appendChild(sel);
      }
    } else if (col.type === 'select') {
      // ── Select-поля (dept, sector, project, stage) ──
      if (col.readOnly) {
        // Read-only select: отображаем как текст (редактирование через модалку)
        td.style.cssText = 'padding:6px 8px;vertical-align:middle;';
        td.textContent = t[col.field] || '';
      } else {
        const sel = document.createElement('select');
        sel.className = 'cell-select';
        sel.dataset.field = col.field;
        if (col.parentField) sel.dataset.parentField = col.parentField;
        if (col.parentDirKey) sel.dataset.parentDirKey = col.parentDirKey;
        if (col.dirKey) sel.dataset.dirKey = col.dirKey;
        // Заполняем варианты из справочника, учитывая каскадную зависимость
        fillSelect(
          sel,
          col.dirKey,
          t[col.field],
          col.parentField ? t[col.parentField] : null,
          col.parentDirKey,
        );
        if (isFromPP) {
          // ПП-записи: select заблокирован — поля из ПП нельзя менять
          sel.disabled = true;
        } else {
          // Обычные записи: при изменении — каскад + автосохранение
          sel.addEventListener('change', () => {
            // При смене отдела — обновляем список секторов
            if (col.field === 'dept') {
              const s = tr.querySelector("select[data-field='sector']");
              if (s) fillSelect(s, 'sector', null, sel.value, 'dept');
            }
            // Каскад: project→stage (этапы фильтруются по проекту из ЕТБД)
            if (col.field === 'project') {
              const s = tr.querySelector("select[data-field='stage']");
              if (s) fillSelect(s, 'stage', null, sel.value, 'project');
            }
            saveTask(t.id, tr);
          });
        }
        td.appendChild(sel);
      }
      // ФИО нач. сектора серым под select
      if (col.extraField) {
        const sectorCode = t[col.field] || '';
        const sectorEntry = (dirs['_ids_sector'] || []).find((s) => s.value === sectorCode);
        const headName = sectorEntry ? sectorEntry.head_name || '' : '';
        if (headName) {
          const extra = document.createElement('div');
          extra.style.cssText =
            'font-size:11px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
          extra.textContent = headName;
          td.appendChild(extra);
        }
      }
    } else {
      // ── Read-only date (Сроки согласно ПП) ──
      if (col.readOnly && col.type === 'date') {
        td.style.cssText = 'padding:6px 8px;vertical-align:middle;text-align:center;';
        const v = t[col.field] || '';
        td.textContent = v ? v.split('-').reverse().join('.') : '';
        tr.appendChild(td);
        return; // forEach continue
      }
      // ── Read-only text (work_number — авто-генерация) ──
      if (col.readOnly && col.type === 'text') {
        td.style.cssText = 'padding:6px 8px;vertical-align:middle;';
        td.textContent = t[col.field] || '';
        tr.appendChild(td);
        return;
      }
      // ── Text/date поля (justification, description, etc.) ──
      // text → textarea, date → input[type=date]
      const inp =
        col.type === 'text' ? document.createElement('textarea') : document.createElement('input');
      inp.className = 'cell-edit';
      inp.dataset.field = col.field;
      if (col.type === 'date') {
        inp.type = 'date';
        // Для ПП-записей блокируем все date-поля кроме date_start/date_end
        const ppAllowedInline = new Set(['date_start', 'date_end']);
        if (isFromPP && !ppAllowedInline.has(col.field)) {
          inp.readOnly = true;
          inp.tabIndex = -1;
        }
      }
      inp.value = t[col.field] || '';
      // Автовысота textarea при вводе текста
      if (inp.tagName === 'TEXTAREA') {
        inp.rows = 1;
        inp.addEventListener('input', () => {
          requestAnimationFrame(() => {
            inp.style.height = 'auto';
            inp.style.height = inp.scrollHeight + 'px';
          });
        });
      }
      // Для ПП-записей блокируем все поля кроме разрешённых (date_start, date_end)
      const ppAllowedFields = new Set(['date_start', 'date_end']);
      if (isFromPP && !ppAllowedFields.has(col.field)) {
        inp.readOnly = true;
        inp.tabIndex = -1;
      }
      // Обработчик изменения — автосохранение + логика пересчёта часов при смене дат
      inp.addEventListener('change', async () => {
        // ПП-поля (кроме дат) — игнорируем
        if (isFromPP && !ppAllowedFields.has(col.field)) return;
        if (col.field === 'date_start' || col.field === 'date_end') {
          // Если есть исполнители и диапазон дат расширился — предупреждаем
          const hasExecutors = (t.executors_list && t.executors_list.length > 0) || t.executor;
          if (hasExecutors) {
            const dsInp = tr.querySelector("input[data-field='date_start']");
            const deInp = tr.querySelector("input[data-field='date_end']");
            const newStart = dsInp?.value || t.date_start;
            const newEnd = deInp?.value || t.date_end;
            // Вычисляем добавленные месяцы (для распределения часов)
            const oldKeys = getTaskMonthKeys(t.date_start, t.date_end, t.deadline);
            const newKeys = getTaskMonthKeys(newStart, newEnd, t.deadline);
            const addedMonths = newKeys.filter((k) => !oldKeys.includes(k));
            if (addedMonths.length > 0) {
              // Показываем модал подтверждения расширения дат
              showDateChangeModal(
                addedMonths.length,
                async (confirmed) => {
                  if (confirmed) {
                    await saveTask(t.id, tr);
                    await loadTasks();
                    // Открываем модал редактирования для настройки часов по новым месяцам
                    const updatedTask = tasks.find((task) => task.id === t.id);
                    if (updatedTask) openEditTaskModal(updatedTask);
                  } else {
                    // Откат значения при отмене
                    inp.value = t[col.field] || '';
                  }
                },
                t.id,
                tr,
              );
              return;
            }
          }
        }
        // Автосохранение задачи на сервер
        await saveTask(t.id, tr);
      });
      td.appendChild(inp);
      // Бейдж снимка месяца под полем «Окончание» (только для date_end)
      if (col.field === 'date_end') {
        td.classList.add('deadline-cell');
        const badge = document.createElement('span');
        badge.className = 'status-badge';
        badge.dataset.role = 'snap-badge';
        _fillSnapBadge(badge, _snapBucketOf(t.id));
        td.appendChild(badge);
      }
    }
    tr.appendChild(td);
    // Вставляем «Код строки» и «Наряд-заказ» после «Проект» (idx=0 → project)
    if (idx === 0) {
      tr.appendChild(rcTd);
      tr.appendChild(woTd);
    }
  });

  // ── Колонки «Сроки согласно ПП» — read-only текст из pp_date_* ──
  const _fmtD = (v) => (v ? v.split('-').reverse().join('.') : '');
  const ppDsTd = document.createElement('td');
  ppDsTd.dataset.colIdx = '14';
  ppDsTd.dataset.label = 'Начало (ПП)';
  ppDsTd.style.cssText = 'padding:6px 8px;vertical-align:middle;text-align:center;';
  ppDsTd.textContent = _fmtD(t.pp_date_start);
  tr.appendChild(ppDsTd);
  const ppDeTd = document.createElement('td');
  ppDeTd.dataset.colIdx = '15';
  ppDeTd.dataset.label = 'Окончание (ПП)';
  ppDeTd.style.cssText = 'padding:6px 8px;vertical-align:middle;text-align:center;';
  ppDeTd.textContent = _fmtD(t.pp_date_end);
  tr.appendChild(ppDeTd);

  // ── Колонка «Действия» — hover иконки ──
  // При наведении на строку справа появляются иконки-кнопки
  const actTd = document.createElement('td');
  actTd.className = 'actions-cell td-actions-hover';
  actTd.dataset.label = 'Действия';
  actTd.dataset.colIdx = '16';
  actTd.style.display = 'table-cell';

  const rowEditable = _canModify(t.dept, t.sector);
  const actWrap = document.createElement('div');
  actWrap.className = 'row-actions';

  if (rowEditable) {
    const editBtn = document.createElement('button');
    editBtn.className = 'row-action-btn' + (isFromPP ? ' btn-locked' : '');
    editBtn.innerHTML = isFromPP ? '<i class="fas fa-lock"></i>' : '<i class="fas fa-pen"></i>';
    // Замочек означает «часть полей зафиксирована ПП»:
    // название/номер/этап/обоснование менять нельзя — они приходят из ПП.
    editBtn.title = isFromPP
      ? 'Задача из ПП — часть полей заблокирована (название, № работы, этап, обоснование). Можно менять даты, исполнителей, план-часы.'
      : 'Редактировать';
    editBtn.addEventListener('mousedown', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openEditTaskModal(t);
    });
    actWrap.appendChild(editBtn);
  }

  const repBtn = document.createElement('button');
  repBtn.className = 'row-action-btn btn-report' + (t.has_reports ? ' has-report' : '');
  repBtn.innerHTML = '<i class="fas fa-clipboard-check"></i>';
  repBtn.title = 'Отчёт';
  repBtn.onclick = () => openReportModal(t);
  actWrap.appendChild(repBtn);

  const depsBtn = document.createElement('button');
  depsBtn.className = 'row-action-btn btn-deps';
  depsBtn.innerHTML = '<i class="fas fa-link"></i>';
  depsBtn.title = 'Зависимости';
  depsBtn.onclick = () => openDepsModal(t);
  actWrap.appendChild(depsBtn);

  if (rowEditable) {
    const delBtn = document.createElement('button');
    delBtn.className = 'row-action-btn btn-delete';
    delBtn.innerHTML = '<i class="fas fa-trash"></i>';
    delBtn.title = 'Удалить';
    delBtn.onclick = () => deleteTask(t.id, tr);
    actWrap.appendChild(delBtn);
  }

  actTd.appendChild(actWrap);
  tr.appendChild(actTd);
  return tr;
}

// Заполняет <select> вариантами из справочника dirs[dirKey]
// parentVal/parentDirKey — фильтрация дочерних записей по родительскому значению
function fillSelect(sel, dirKey, selectedVal, parentVal, parentDirKey) {
  sel.innerHTML = "<option value=''>—</option>";
  // Исполнители хранятся в _ids_employees (реальные Employee), а не в _ids_executor
  const allItems =
    dirKey === 'executor' ? dirs['_ids_employees'] || [] : dirs[`_ids_${dirKey}`] || [];
  let items = allItems;
  if (dirKey === 'executor') {
    // Исполнители: фильтруем по сектору (если parentDirKey='sector'), иначе по отделу (если parentDirKey='dept')
    if (parentVal && parentDirKey === 'sector') {
      items = allItems.filter((e) => e.sector === parentVal);
    } else if (parentVal && parentDirKey === 'dept') {
      items = allItems.filter((e) => e.dept === parentVal);
    }
    // Фантомная опция для текущего значения не из отфильтрованного списка
    if (selectedVal && !items.find((e) => e.value === selectedVal)) {
      const ghost = document.createElement('option');
      ghost.value = selectedVal;
      ghost.textContent = selectedVal;
      ghost.selected = true;
      sel.appendChild(ghost);
    }
  } else if (dirKey === 'stage' && parentDirKey === 'project') {
    // Этапы: без выбранного проекта — пустой список
    if (!parentVal) {
      items = [];
    } else {
      const projItem = (dirs['_ids_project'] || []).find((i) => i.value === parentVal);
      if (projItem) items = allItems.filter((i) => i.project_id === projItem.id);
      else items = [];
    }
    // Фантомная опция для текущего значения из другого проекта
    if (selectedVal && !items.find((i) => i.value === selectedVal)) {
      const o = document.createElement('option');
      o.value = selectedVal;
      o.textContent = selectedVal;
      o.selected = true;
      o.style.color = 'var(--muted)';
      sel.appendChild(o);
    }
  } else if (parentVal && parentDirKey) {
    const parentItem = (dirs[`_ids_${parentDirKey}`] || []).find((i) => i.value === parentVal);
    if (parentItem) items = allItems.filter((i) => i.parent_id === parentItem.id);
    // Фантомная опция для текущего значения из другого родителя
    if (selectedVal && !items.find((i) => i.value === selectedVal)) {
      const ghost = allItems.find((i) => i.value === selectedVal);
      const o = document.createElement('option');
      o.value = selectedVal;
      o.textContent = selectedVal;
      o.selected = true;
      o.style.color = 'var(--muted)';
      sel.appendChild(o);
    }
  }
  items.forEach((item) => {
    const o = document.createElement('option');
    o.value = item.value;
    // Для этапов показываем label (номер + название) вместо голого номера
    o.textContent = item.label || item.value;
    if (item.value === selectedVal) o.selected = true;
    // Ограничения по роли: dept_head/sect_head/dept_deputy могут выбрать только свой отдел
    if (
      dirKey === 'dept' &&
      !IS_ADMIN &&
      USER_DEPT &&
      item.value !== USER_DEPT &&
      ['dept_head', 'dept_deputy', 'sector_head'].includes(USER_ROLE)
    ) {
      o.disabled = true;
      o.style.color = 'var(--muted)';
    }
    // sector_head может выбрать только свой сектор
    if (
      dirKey === 'sector' &&
      !IS_ADMIN &&
      USER_SECTOR &&
      item.value !== USER_SECTOR &&
      USER_ROLE === 'sector_head'
    ) {
      o.disabled = true;
      o.style.color = 'var(--muted)';
    }
    sel.appendChild(o);
  });
  // Обновляем кастомный dropdown (триггер-текст) после перезаполнения
  if (typeof refreshCustomDropdown === 'function') refreshCustomDropdown(sel);
}

// Собирает данные из ячеек строки таблицы в объект для отправки на сервер
function getRowData(tr) {
  const data = {};
  tr.querySelectorAll('.cell-edit,.cell-select').forEach((inp) => {
    if (inp.dataset.field && inp.dataset.field !== 'plan_hours') {
      data[inp.dataset.field] = inp.value || null;
    }
  });
  const badge = tr.querySelector('.type-badge');
  if (badge) data.task_type = badge.textContent;
  const phInp = tr.querySelector("input[data-field='plan_hours']");
  if (phInp && selectedMonth != null) {
    const key = `${selectedYear}-${String(selectedMonth).padStart(2, '0')}`;
    data.plan_hours_update = {};
    data.plan_hours_update[key] = parseFloat(phInp.value) || 0;
  }
  // Оптимистичная блокировка: передаём timestamp последнего обновления
  if (tr.dataset.updatedAt) data.updated_at = tr.dataset.updatedAt;
  return data;
}

// Сохраняет изменения задачи на сервер (PUT /api/tasks/<id>/) из inline-ячеек
async function saveTask(id, tr) {
  const data = getRowData(tr);
  tr.style.outline = '1px solid rgba(59,130,246,0.4)';
  try {
    const res = await fetch(`/api/tasks/${id}/`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify(data),
    });
    if (res.status === 409) {
      const err = await res.json();
      tr.style.outline = '1px solid rgba(239,68,68,0.6)';
      setTimeout(() => {
        tr.style.outline = '';
      }, 3000);
      tr.querySelectorAll('td').forEach(function (td) {
        flashCell(td, 'error');
      });
      notify('⚠ ' + (err.message || 'Конфликт: данные изменены другим пользователем'), 'err');
      return;
    }
    if (!res.ok) throw new Error('HTTP ' + res.status);
    // Обновляем локальный timestamp для следующего PUT
    try {
      const ok = await res.json();
      if (ok && ok.updated_at) tr.dataset.updatedAt = ok.updated_at;
    } catch (_) {
      /* ignored */
    }
    tr.style.outline = '1px solid rgba(34,197,94,0.5)';
    setTimeout(() => {
      tr.style.outline = '';
    }, 800);
    tr.querySelectorAll('td').forEach(function (td) {
      flashCell(td);
    });
  } catch (e) {
    tr.style.outline = '1px solid rgba(239,68,68,0.6)';
    setTimeout(() => {
      tr.style.outline = '';
    }, 3000);
    tr.querySelectorAll('td').forEach(function (td) {
      flashCell(td, 'error');
    });
    notify('Ошибка сохранения: ' + e.message, 'err');
  }
}

// Удаляет задачу (DELETE /api/tasks/<id>/) с подтверждением + анимация исчезновения
async function deleteTask(id, tr) {
  if (!(await confirmDialog('Удалить задачу?', 'Удаление'))) return;
  try {
    const res = await fetch(`/api/tasks/${id}/`, { method: 'DELETE', headers: apiHeaders() });
    if (!res.ok) {
      let msg = 'Ошибка удаления';
      try {
        const e = await res.json();
        if (e.error) msg = e.error;
      } catch (_) {
        /* ignored */
      }
      notify(msg, 'err');
      return;
    }
    // Удаляем из локального массива задач
    tasks = tasks.filter((t) => t.id !== id);
    animateRowExit(tr, function () {
      tr.remove();
      document.querySelectorAll('#taskBody .num-cell').forEach((td, i) => {
        const cb = td.querySelector('input[type="checkbox"]');
        if (cb) {
          cb.nextSibling
            ? (cb.nextSibling.textContent = ' ' + (i + 1))
            : td.appendChild(document.createTextNode(' ' + (i + 1)));
        } else {
          td.textContent = i + 1;
        }
      });
    });
    notify('Задача удалена', 'ok');
  } catch (e) {
    notify('Ошибка сети: ' + e.message, 'err');
  }
}

// ── BULK SELECT / DELETE ──────────────────────────────────────────────────
var _bulkMode = false;
var _bulkSelected = new Set();

function toggleBulkMode() {
  _bulkMode = !_bulkMode;
  _bulkSelected.clear();
  var btn = document.getElementById('bulkModeBtn');
  if (btn) btn.classList.toggle('active', _bulkMode);
  // Добавляем/убираем чекбоксы в num-cell
  document.querySelectorAll('#taskBody tr').forEach(function (tr) {
    var numCell = tr.querySelector('.num-cell');
    if (!numCell) return;
    var existing = numCell.querySelector('.bulk-cb');
    if (_bulkMode && !existing) {
      var cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = 'bulk-cb';
      cb.onchange = function () {
        var id = parseInt(tr.dataset.id);
        if (cb.checked) _bulkSelected.add(id);
        else _bulkSelected.delete(id);
        updateBulkBar();
      };
      numCell.insertBefore(cb, numCell.firstChild);
    } else if (!_bulkMode && existing) {
      existing.remove();
    }
  });
  updateBulkBar();
}

function updateBulkBar() {
  var count = document.getElementById('bulkCount');
  if (count) count.textContent = _bulkSelected.size;
  var bar = document.getElementById('bulkBar');
  if (bar) bar.classList.toggle('visible', _bulkMode && _bulkSelected.size > 0);
}

function bulkSelectAll() {
  var cbs = document.querySelectorAll('#taskBody .bulk-cb');
  var allChecked = _bulkSelected.size === cbs.length && cbs.length > 0;
  cbs.forEach(function (cb) {
    cb.checked = !allChecked;
    var id = parseInt(cb.closest('tr').dataset.id);
    if (!allChecked) _bulkSelected.add(id);
    else _bulkSelected.delete(id);
  });
  updateBulkBar();
}

function bulkDeselectAll() {
  _bulkSelected.clear();
  document.querySelectorAll('#taskBody .bulk-cb').forEach(function (cb) {
    cb.checked = false;
  });
  updateBulkBar();
}

function bulkExport() {
  if (_bulkSelected.size === 0) return;
  var selected = tasks.filter(function (t) {
    return _bulkSelected.has(t.id);
  });
  // Fallback CSV export for selected rows
  var cols = ['row_code', 'dept', 'project', 'work_name', 'executor', 'date_start', 'date_end'];
  var headers = [
    'Код строки',
    'Отдел',
    'Проект',
    'Наименование',
    'Исполнитель',
    'Дата начала',
    'Дата окончания',
  ];
  var csv = '\uFEFF' + headers.join(';') + '\n';
  selected.forEach(function (r) {
    csv +=
      cols
        .map(function (c) {
          return '"' + String(r[c] || '').replace(/"/g, '""') + '"';
        })
        .join(';') + '\n';
  });
  var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'СП_выбранные.csv';
  a.click();
  URL.revokeObjectURL(a.href);
  notify('Экспортировано задач: ' + selected.length, 'ok');
}

async function bulkDelete() {
  if (_bulkSelected.size === 0) return;
  if (!(await confirmDialog('Удалить ' + _bulkSelected.size + ' задач(и)?', 'Массовое удаление')))
    return;
  try {
    var res = await fetch('/api/tasks/bulk_delete/', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ ids: Array.from(_bulkSelected) }),
    });
    if (!res.ok) {
      var e = await res.json().catch(function () {
        return {};
      });
      notify(e.error || 'Ошибка удаления', 'err');
      return;
    }
    var data = await res.json();
    notify('Удалено задач: ' + data.deleted, 'ok');
    _bulkSelected.clear();
    _bulkMode = false;
    var btn = document.getElementById('bulkModeBtn');
    if (btn) btn.classList.remove('active');
    updateBulkBar();
    await loadTasks();
  } catch (e) {
    notify('Ошибка сети: ' + e.message, 'err');
  }
}

// ── TYPE MODAL ────────────────────────────────────────────────────────────
function openTypeModal() {
  document.getElementById('typeModal').classList.add('open');
}
function closeTypeModal() {
  document.getElementById('typeModal').classList.remove('open');
}
function selectTypeAndProceed(el) {
  pendingTaskType = el.dataset.type;
  closeTypeModal();
  openNewTaskModal(pendingTaskType);
}

// ── INLINE NEW ROW — добавление задачи прямо в таблице (без модала) ───────
let _addingTaskRow = false; // Флаг: строка добавления уже показана

const TASK_TYPES = [
  'Разработка',
  'Выпуск нового документа',
  'Корректировка документа',
  'Сопровождение (ОКАН)',
];

function openInlineNewRow() {
  // Если включена настройка «Модальное окно» — открываем выбор типа → модалку
  if (colSettings && colSettings.pp_input_modal) {
    openTypeModal();
    return;
  }
  if (_addingTaskRow) {
    const r = document.getElementById('taskNewRow');
    if (r) {
      r.scrollIntoView({ behavior: 'smooth', block: 'center' });
      r.querySelector('select,input')?.focus();
    }
    return;
  }
  _addingTaskRow = true;

  const tbody = document.getElementById('taskBody');
  const tr = document.createElement('tr');
  tr.id = 'taskNewRow';
  tr.style.cssText = 'background:rgba(59,130,246,0.07);outline:2px solid rgba(59,130,246,0.4);';

  // № колонка
  const numTd = document.createElement('td');
  numTd.className = 'num-cell';
  numTd.dataset.colIdx = '0';
  numTd.innerHTML = '<span style="color:var(--accent);font-weight:700;">+</span>';
  tr.appendChild(numTd);

  // Колонки: project (ci:1), код строки (ci:2), stage, ...
  // Код строки вставляется отдельно после project
  const colDefs = [
    { id: 'inr-project', type: 'select', dirKey: 'project', ci: 1 },
    { id: '_rc_', type: 'static', ci: 2 }, // Код строки — read-only placeholder
    { id: '_wo_', type: 'static_text', ci: 3, text: '(авто)' }, // Наряд-заказ — read-only, авто
    {
      id: 'inr-stage',
      type: 'select',
      dirKey: 'stage',
      parentId: 'inr-project',
      parentDirKey: 'project',
      ci: 4,
    },
    { id: '_wn_', type: 'static_text', ci: 5, text: '(авто)' }, // № работы — read-only, авто
    { id: 'inr-justification', type: 'text', placeholder: 'Обоснование', ci: 6 },
    { id: 'inr-description', type: 'text', placeholder: 'Обозначение', ci: 7 },
    { id: 'inr-work_name', type: 'text', placeholder: 'Наименование', ci: 8 },
    { id: 'inr-dept', type: 'select', dirKey: 'dept', ci: 9 },
    {
      id: 'inr-sector',
      type: 'select',
      dirKey: 'sector',
      parentId: 'inr-dept',
      parentDirKey: 'dept',
      ci: 10,
    },
  ];

  // Авто-значения из профиля пользователя для dept/sector
  const _inrDefDept =
    ['dept_head', 'dept_deputy', 'sector_head'].includes(USER_ROLE) && USER_DEPT ? USER_DEPT : null;
  const _inrDefSector = USER_ROLE === 'sector_head' && USER_SECTOR ? USER_SECTOR : null;

  colDefs.forEach((def) => {
    const td = document.createElement('td');
    if (def.ci !== undefined) td.dataset.colIdx = String(def.ci);
    if (def.type === 'static') {
      // Код строки — read-only, авто из ЕТБД
      td.style.cssText =
        'padding:4px 6px;vertical-align:middle;text-align:center;color:var(--muted);';
      td.textContent = '(авто)';
      // Hidden select для task_type — используется при отправке
      const typeSel = document.createElement('select');
      typeSel.id = 'inr-task_type';
      typeSel.style.display = 'none';
      TASK_TYPES.forEach((t) => {
        const o = document.createElement('option');
        o.value = t;
        o.textContent = t;
        typeSel.appendChild(o);
      });
      td.appendChild(typeSel);
      tr.appendChild(td);
      return;
    }
    if (def.type === 'static_text') {
      td.style.cssText =
        'padding:4px 6px;vertical-align:middle;text-align:center;color:var(--muted);';
      td.textContent = def.text || '—';
      tr.appendChild(td);
      return;
    }
    if (def.type === 'select') {
      const sel = document.createElement('select');
      sel.id = def.id;
      sel.className = 'cell-select';
      // Автовыбор своего отдела/сектора из профиля
      const defVal =
        def.id === 'inr-dept' ? _inrDefDept : def.id === 'inr-sector' ? _inrDefSector : null;
      // Родительское значение для каскада (sector←dept, stage←project)
      let defParent = null;
      if (def.id === 'inr-sector') defParent = _inrDefDept;
      else if (def.parentId) {
        const pSel = document.getElementById(def.parentId);
        defParent = pSel ? pSel.value : null;
      }
      fillSelect(sel, def.dirKey, defVal, defParent, def.parentDirKey || null);
      // Каскад: dept→sector→executor, project→stage
      if (def.id === 'inr-dept') {
        sel.addEventListener('change', () => {
          const secSel = document.getElementById('inr-sector');
          if (secSel) fillSelect(secSel, 'sector', null, sel.value, 'dept');
          // При смене отдела сброс сектора → показываем всех сотрудников отдела
          const execSel = document.getElementById('inr-executor');
          if (execSel) fillSelect(execSel, 'executor', null, sel.value, 'dept');
        });
      }
      if (def.id === 'inr-sector') {
        sel.addEventListener('change', () => {
          const execSel = document.getElementById('inr-executor');
          const deptVal = document.getElementById('inr-dept')?.value || '';
          if (execSel) {
            if (sel.value) {
              fillSelect(execSel, 'executor', null, sel.value, 'sector');
            } else {
              fillSelect(execSel, 'executor', null, deptVal, 'dept');
            }
          }
        });
      }
      // Каскад: project→stage (этапы фильтруются по проекту, ЕТБД)
      if (def.id === 'inr-project') {
        sel.addEventListener('change', () => {
          const stageSel = document.getElementById('inr-stage');
          if (stageSel) fillSelect(stageSel, 'stage', null, sel.value, 'project');
          // При смене проекта сбрасываем код строки и наряд-заказ
          const rcCell = tr.querySelector('td[data-col-idx="2"]');
          const woCell = tr.querySelector('td[data-col-idx="3"]');
          if (rcCell) {
            rcCell.childNodes[0].textContent = '(авто)';
          }
          if (woCell) {
            woCell.textContent = '(авто)';
          }
        });
      }
      // При смене этапа — обновляем код строки и наряд-заказ из ЕТБД
      if (def.id === 'inr-stage') {
        sel.addEventListener('change', () => {
          const stgItem = (dirs['_ids_stage'] || []).find((s) => s.value === sel.value);
          const rcCell = tr.querySelector('td[data-col-idx="2"]');
          const woCell = tr.querySelector('td[data-col-idx="3"]');
          if (rcCell) {
            rcCell.childNodes[0].textContent = stgItem ? stgItem.row_code || '(авто)' : '(авто)';
          }
          if (woCell) {
            woCell.textContent = stgItem ? stgItem.work_order || '(авто)' : '(авто)';
          }
        });
      }
      td.appendChild(sel);
    } else {
      const ta = document.createElement('textarea');
      ta.id = def.id;
      ta.className = 'cell-edit';
      ta.placeholder = def.placeholder || '';
      ta.rows = 1;
      ta.style.cssText = 'resize:none;overflow:hidden;';
      ta.addEventListener('input', () => {
        requestAnimationFrame(() => {
          ta.style.height = 'auto';
          ta.style.height = ta.scrollHeight + 'px';
        });
      });
      td.appendChild(ta);
    }
    tr.appendChild(td);
  });

  // Исполнитель (select — одиночный при создании)
  const execTd = document.createElement('td');
  execTd.dataset.colIdx = '11';
  const execSel = document.createElement('select');
  execSel.id = 'inr-executor';
  execSel.className = 'cell-select';
  fillSelect(execSel, 'executor', null, null, null);
  execTd.appendChild(execSel);
  tr.appendChild(execTd);

  // Сроки выполнения — date_start, date_end (редактируемые)
  const spDsTd = document.createElement('td');
  spDsTd.dataset.colIdx = '12';
  const spDsInp = document.createElement('input');
  spDsInp.type = 'date';
  spDsInp.id = 'inr-date_start';
  spDsInp.className = 'cell-edit';
  spDsTd.appendChild(spDsInp);
  tr.appendChild(spDsTd);
  const spDeTd = document.createElement('td');
  spDeTd.dataset.colIdx = '13';
  const spDeInp = document.createElement('input');
  spDeInp.type = 'date';
  spDeInp.id = 'inr-date_end';
  spDeInp.className = 'cell-edit';
  spDeTd.appendChild(spDeInp);
  tr.appendChild(spDeTd);

  // Сроки согласно ПП — read-only (пусто при создании)
  const ppDsTd = document.createElement('td');
  ppDsTd.dataset.colIdx = '14';
  ppDsTd.style.cssText = 'font-size:11px;color:var(--muted);padding:4px 6px;text-align:center;';
  ppDsTd.textContent = '—';
  tr.appendChild(ppDsTd);
  const ppDeTd = document.createElement('td');
  ppDeTd.dataset.colIdx = '15';
  ppDeTd.style.cssText = 'font-size:11px;color:var(--muted);padding:4px 6px;text-align:center;';
  ppDeTd.textContent = '—';
  tr.appendChild(ppDeTd);

  // Кнопки ✓ / ✕
  const actTd = document.createElement('td');
  actTd.dataset.colIdx = '16';
  actTd.style.cssText = 'white-space:nowrap;padding:6px 8px;vertical-align:middle;';
  actTd.innerHTML = `
    <button id="taskNewRowSave" title="Сохранить" style="background:var(--success);color:#fff;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;font-size:13px;margin-right:2px;">✓</button>
    <button id="taskNewRowCancel" title="Отмена" style="background:transparent;color:var(--danger);border:1px solid var(--danger);border-radius:4px;padding:4px 8px;cursor:pointer;font-size:13px;">✕</button>
  `;
  tr.appendChild(actTd);

  // Сначала прокручиваем вверх, потом вставляем строку — без рывка
  const wrap = document.getElementById('tableView');
  if (wrap) wrap.scrollTop = 0;
  tbody.prepend(tr);
  animateRowEnter(tr);

  // Инициализируем кастомные dropdown-ы для новой строки
  if (typeof initCustomDropdowns === 'function') initCustomDropdowns(tr);

  const firstInput = tr.querySelector('.cd-trigger, textarea, input');
  if (firstInput) firstInput.focus();

  // Сохранение
  async function doSaveNewTaskRow() {
    const saveBtn = document.getElementById('taskNewRowSave');
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = '...';
    }

    const executor = document.getElementById('inr-executor')?.value || null;

    const _v = (id) => document.getElementById(id)?.value || '';
    const data = {
      task_type: _v('inr-task_type') || TASK_TYPES[0],
      dept: _v('inr-dept'),
      sector: _v('inr-sector'),
      project: _v('inr-project'),
      stage: _v('inr-stage'),
      work_name: _v('inr-work_name'),
      justification: _v('inr-justification'),
      description: _v('inr-description'),
      executor: executor || '',
      date_start: _v('inr-date_start') || null,
      date_end: _v('inr-date_end') || null,
      plan_hours: {},
      executors_list: executor ? [{ name: executor, hours: {} }] : [],
    };

    try {
      const res = await fetch('/api/tasks/create/', {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const resp = await res.json();
      _spPinnedRowId = resp.id || null;
      _spPinKeep = true;
      _addingTaskRow = false;
      tr.remove();
      await loadTasks();
      notify('✓ Задача создана', 'ok');
    } catch (e) {
      notify('Ошибка создания задачи', 'err');
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = '✓';
      }
    }
  }

  document.getElementById('taskNewRowSave').addEventListener('click', doSaveNewTaskRow);
  document.getElementById('taskNewRowCancel').addEventListener('click', () => {
    _addingTaskRow = false;
    tr.remove();
  });

  // Enter в textarea/input → сохранить (Shift+Enter — перенос строки в textarea)
  tr.querySelectorAll('input').forEach((inp) => {
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        doSaveNewTaskRow();
      }
      if (e.key === 'Escape') {
        _addingTaskRow = false;
        tr.remove();
      }
    });
  });
  tr.querySelectorAll('textarea').forEach((ta) => {
    ta.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        _addingTaskRow = false;
        tr.remove();
      }
    });
  });
}

// ── NEW TASK FORM MODAL — модал создания/редактирования задачи ─────────────
let editingTaskId = null; // ID редактируемой задачи (null = создание)
let _editingTaskOriginal = null; // Исходные данные задачи (для сравнения)

// Сброс состояния при закрытии модалки через ESC (base.html снимает .open)
// Ссылка хранится на уровне модуля, чтобы можно было .disconnect() перед повторным созданием
var _newTaskModalObserver = null;
(function () {
  const ntm = document.getElementById('newTaskModal');
  if (ntm) {
    if (_newTaskModalObserver) _newTaskModalObserver.disconnect();
    _newTaskModalObserver = new MutationObserver(function () {
      if (!ntm.classList.contains('open') && editingTaskId !== null) {
        editingTaskId = null;
        _editingTaskOriginal = null;
      }
    });
    _newTaskModalObserver.observe(ntm, { attributes: true, attributeFilter: ['class'] });
  }
})();

// Открывает модал создания новой задачи; taskType — тип задачи, prefill — начальные значения
function openNewTaskModal(taskType, prefill) {
  editingTaskId = null;
  newTaskExecutorsList = [];
  const cls = taskType.toLowerCase().split(' ')[0];
  document.getElementById('newTaskTypeBadgeWrap').innerHTML =
    `<span class="type-badge ${cls}">${taskType}</span>`;
  document.getElementById('newTaskModalTitle').textContent = 'Новая задача';
  const rcEl2 = document.getElementById('newTaskRowCode');
  if (rcEl2) {
    rcEl2.textContent = '';
    rcEl2.style.display = 'none';
  }
  document.getElementById('newTaskSubmitBtn').textContent = '✓ Создать задачу';

  // Авто-значение отдела/сектора: из prefill (редактирование) или из профиля (новая задача)
  const _ntDefDept =
    prefill?.dept ||
    (['dept_head', 'dept_deputy', 'sector_head'].includes(USER_ROLE) ? USER_DEPT : null);
  const _ntDefSector = prefill?.sector || (USER_ROLE === 'sector_head' ? USER_SECTOR : null);
  populateFormSelect(document.getElementById('nt-dept'), 'dept', _ntDefDept, null, null);
  populateFormSelect(
    document.getElementById('nt-sector'),
    'sector',
    _ntDefSector,
    _ntDefDept || null,
    'dept',
  );
  populateFormSelect(
    document.getElementById('nt-project'),
    'project',
    prefill?.project || null,
    null,
    null,
  );
  populateFormSelect(
    document.getElementById('nt-stage'),
    'stage',
    prefill?.stage || null,
    prefill?.project || null,
    'project',
  );
  populateFormSelect(document.getElementById('nt-executor-select'), 'executor', null, null, null);
  [
    'work_name',
    'justification',
    'description',
    'date_start',
    'date_end',
    'deadline',
    'actions',
  ].forEach((f) => {
    const el = document.getElementById(`nt-${f}`);
    if (el) el.value = prefill?.[f] || '';
  });

  document.getElementById('nt-plan-months-wrap').innerHTML = '';
  document.getElementById('nt-plan_hours_single').value = '';
  document.getElementById('nt-plan-months-wrap').style.display = 'none';
  document.getElementById('nt-plan-single-wrap').style.display = 'none';
  document.getElementById('nt-labor-row').style.display = 'none';

  if (prefill?.date_start || prefill?.date_end) onNewTaskDateChange(prefill?.plan_hours_all || {});
  else updateTotalHours();
  renderNewTaskExecutorsList();
  document.getElementById('nt-actions-wrap').style.display = '';
  _applyPPLock(false);
  document.getElementById('newTaskModal').classList.add('open');
}

// Открывает модал редактирования существующей задачи; t — объект задачи
function openEditTaskModal(t) {
  editingTaskId = t.id;
  _editingTaskOriginal = t;
  // Копия, чтобы не мутировать исходный объект при отмене
  newTaskExecutorsList = (t.executors_list || []).map(function (ex) {
    return Object.assign({}, ex);
  });
  pendingTaskType = t.task_type;
  const cls = (t.task_type || '').toLowerCase().split(' ')[0];
  document.getElementById('newTaskTypeBadgeWrap').innerHTML =
    `<span class="type-badge ${cls}">${t.task_type || ''}</span>`;
  document.getElementById('newTaskModalTitle').textContent = `Редактирование задачи #${t.id}`;
  const rcEl = document.getElementById('newTaskRowCode');
  if (rcEl) {
    rcEl.textContent = t.row_code ? `Код строки: ${t.row_code}` : '';
    rcEl.style.display = t.row_code ? '' : 'none';
  }
  document.getElementById('newTaskSubmitBtn').textContent = '💾 Сохранить изменения';

  populateFormSelect(document.getElementById('nt-dept'), 'dept', t.dept || null, null, null);
  populateFormSelect(
    document.getElementById('nt-sector'),
    'sector',
    t.sector || null,
    t.dept || null,
    'dept',
  );
  populateFormSelect(
    document.getElementById('nt-project'),
    'project',
    t.project || null,
    null,
    null,
  );
  populateFormSelect(
    document.getElementById('nt-stage'),
    'stage',
    t.stage || null,
    t.project || null,
    'project',
  );
  populateFormSelect(document.getElementById('nt-executor-select'), 'executor', null, null, null);
  ['work_name', 'justification', 'description', 'date_start', 'date_end', 'deadline'].forEach(
    (f) => {
      const el = document.getElementById(`nt-${f}`);
      if (el) el.value = t[f] || '';
    },
  );

  document.getElementById('nt-actions-wrap').style.display = 'none';
  document.getElementById('nt-plan-months-wrap').innerHTML = '';
  document.getElementById('nt-plan_hours_single').value = '';
  document.getElementById('nt-plan-months-wrap').style.display = 'none';
  document.getElementById('nt-plan-single-wrap').style.display = 'none';
  document.getElementById('nt-labor-row').style.display = 'none';

  if (t.date_start || t.date_end) onNewTaskDateChange(t.plan_hours_all || {});
  else updateTotalHours();
  renderNewTaskExecutorsList();

  // from_pp: запись из ПП, ПП-поля заблокированы
  const isPP = !!t.from_pp;
  _applyPPLock(isPP);

  const ppLaborWrap = document.getElementById('nt-pp-labor-wrap');
  const ppLaborEl = document.getElementById('nt-pp-labor');
  const ppLabor = t.pp_labor || '';
  if (isPP && ppLabor) {
    ppLaborWrap.style.display = '';
    ppLaborEl.textContent = ppLabor + ' ч';
  } else {
    ppLaborWrap.style.display = 'none';
    ppLaborEl.textContent = '—';
  }

  var modal = document.getElementById('newTaskModal');
  modal.classList.add('slideout-mode');
  modal.classList.add('open');
}

// Блокирует ПП-поля в модале (isPP=true: запись из Производственного плана)
function _applyPPLock(isPP) {
  document.getElementById('pp-edit-hint')?.remove();
  const ppAllowed = new Set([
    'nt-date_start',
    'nt-date_end',
    'nt-deadline',
    'nt-plan_hours_single',
    'nt-executor-select',
  ]);
  const formEls = document.querySelectorAll(
    '#newTaskModal .form-input, #newTaskModal .form-select, #newTaskModal .form-textarea',
  );
  formEls.forEach((el) => {
    const allowed =
      ppAllowed.has(el.id) || el.hasAttribute('data-month') || el.hasAttribute('data-exec-index');
    el.disabled = isPP && !allowed;
  });
  const addExecBtn = document.querySelector(
    "#newTaskModal button[onclick='addExecutorToNewTask()']",
  );
  if (addExecBtn) {
    addExecBtn.disabled = false;
    addExecBtn.style.opacity = '';
  }
  if (isPP) {
    const hint = document.createElement('div');
    hint.className = 'pp-edit-hint';
    hint.id = 'pp-edit-hint';
    hint.innerHTML =
      '🔒 Задача перенесена из <b>Производственного плана</b>. ' +
      'Доступно изменение: <b>Исполнители</b>, <b>Дата начала</b>, <b>Дата окончания</b>, <b>План труд (часы)</b>.';
    const body = document.querySelector('#newTaskModal .new-task-body');
    body.insertBefore(hint, body.firstChild);
  }
}

// Закрывает модал создания/редактирования и сбрасывает состояние
function closeNewTaskModal() {
  var modal = document.getElementById('newTaskModal');
  modal.classList.remove('open');
  modal.classList.remove('slideout-mode');
  editingTaskId = null;
  _editingTaskOriginal = null;
  _applyPPLock(false);
  document.getElementById('nt-actions-wrap').style.display = '';
  document.getElementById('nt-pp-labor-wrap').style.display = 'none';
}

// Каскад: при смене отдела → обновляем сектор и исполнителей
function onNewTaskDeptChange() {
  const deptVal = document.getElementById('nt-dept').value;
  populateFormSelect(document.getElementById('nt-sector'), 'sector', null, deptVal, 'dept');
  // При смене отдела сбрасываем сектор → показываем всех сотрудников отдела
  populateFormSelect(
    document.getElementById('nt-executor-select'),
    'executor',
    null,
    deptVal,
    'dept',
  );
}
// Каскад: при смене сектора → обновляем исполнителей (фильтр по сектору или отделу)
function onNewTaskSectorChange() {
  const sectorVal = document.getElementById('nt-sector').value;
  const deptVal = document.getElementById('nt-dept').value;
  if (sectorVal) {
    populateFormSelect(
      document.getElementById('nt-executor-select'),
      'executor',
      null,
      sectorVal,
      'sector',
    );
  } else {
    populateFormSelect(
      document.getElementById('nt-executor-select'),
      'executor',
      null,
      deptVal,
      'dept',
    );
  }
}
function onNewTaskProjectChange() {
  // Каскад: project→stage (этапы фильтруются по проекту из ЕТБД)
  const projVal = document.getElementById('nt-project').value;
  populateFormSelect(document.getElementById('nt-stage'), 'stage', null, projVal, 'project');
  // При смене проекта сбрасываем row_code
  const rcEl = document.getElementById('newTaskRowCode');
  if (rcEl) {
    rcEl.textContent = '';
    rcEl.style.display = 'none';
  }
}

// При изменении дат задачи — перестраиваем поля помесячных часов
function onNewTaskDateChange(prefillHours) {
  const ds = document.getElementById('nt-date_start').value;
  const de = document.getElementById('nt-date_end').value;
  const keys = getTaskMonthKeys(ds, de);
  const wrap = document.getElementById('nt-plan-months-wrap');
  const singleWrap = document.getElementById('nt-plan-single-wrap');
  const totalWrap = document.getElementById('nt-total-wrap');

  if (keys.length > 1) {
    singleWrap.style.display = 'none';
    wrap.style.display = '';
    totalWrap.style.display = '';
    const existing = prefillHours || {};
    wrap.querySelectorAll('input[data-month]').forEach((inp) => {
      if (!prefillHours) existing[inp.dataset.month] = inp.value;
    });
    wrap.innerHTML = '';
    keys.forEach((key) => {
      const [y, m] = key.split('-');
      const label = `${MONTH_NAMES[parseInt(m)]} ${y}`;
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:10px;margin-bottom:8px';
      row.innerHTML = `
        <span style="font-size:16px;color:var(--muted2);width:80px;flex-shrink:0">${label}</span>
        <input type="number" class="form-input" data-month="${key}" placeholder="0"
               style="width:120px" value="${existing[key] || ''}">
        <span style="font-size:15px;color:var(--muted)">ч</span>`;
      row.querySelector('input').addEventListener('input', updateTotalHours);
      wrap.appendChild(row);
    });
    updateTotalHours();
  } else if (keys.length === 1) {
    singleWrap.style.display = '';
    wrap.style.display = 'none';
    wrap.innerHTML = '';
    totalWrap.style.display = '';
    if (prefillHours && keys[0]) {
      document.getElementById('nt-plan_hours_single').value = prefillHours[keys[0]] || '';
    }
    updateTotalHours();
  } else {
    singleWrap.style.display = '';
    wrap.style.display = 'none';
    totalWrap.style.display = 'none';
  }
  renderNewTaskExecutorsList();
}

// Пересчитывает и отображает сумму часов (из исполнителей или помесячных полей)
function updateTotalHours() {
  const execInputs = document.querySelectorAll('#nt-executors-list input[data-exec-index]');
  const monthInputs = document.querySelectorAll('#nt-plan-months-wrap input[data-month]');
  const singleInp = document.getElementById('nt-plan_hours_single');
  const singleVisible =
    singleInp && document.getElementById('nt-plan-single-wrap').style.display !== 'none';
  const hasExec = execInputs.length > 0;
  const hasMonth = monthInputs.length > 0;
  const hasSingle = singleVisible;
  let total = 0;
  if (hasExec && hasMonth) {
    const monthSums = {};
    execInputs.forEach((inp) => {
      const key = inp.dataset.month;
      monthSums[key] = (monthSums[key] || 0) + (parseFloat(inp.value) || 0);
    });
    monthInputs.forEach((inp) => {
      const key = inp.dataset.month;
      const sum = monthSums[key] || 0;
      inp.value = sum > 0 ? sum : '';
      total += sum;
    });
  } else if (hasMonth) {
    monthInputs.forEach((inp) => {
      total += parseFloat(inp.value) || 0;
    });
  } else if (hasExec) {
    execInputs.forEach((inp) => {
      total += parseFloat(inp.value) || 0;
    });
  } else if (hasSingle) {
    // Один месяц — берём значение из простого поля
    total = parseFloat(singleInp.value) || 0;
  }
  document.getElementById('nt-total-hours').textContent = total > 0 ? total + ' ч' : '0 ч';
  if (hasExec || hasMonth || hasSingle) document.getElementById('nt-labor-row').style.display = '';
}

// Заполняет <select> в модале создания/редактирования; аналог fillSelect для формы
function populateFormSelect(sel, dirKey, selectedVal, parentVal, parentDirKey) {
  sel.innerHTML = "<option value=''>—</option>";
  // Исполнители хранятся в _ids_employees (реальные Employee), а не в _ids_executor
  const allItems =
    dirKey === 'executor' ? dirs['_ids_employees'] || [] : dirs[`_ids_${dirKey}`] || [];
  let items = allItems;
  if (dirKey === 'executor') {
    // Исполнители: фильтруем по сектору или отделу
    if (parentVal && parentDirKey === 'sector') {
      items = allItems.filter((e) => e.sector === parentVal);
    } else if (parentVal && parentDirKey === 'dept') {
      items = allItems.filter((e) => e.dept === parentVal);
    }
  } else if (dirKey === 'stage' && parentDirKey === 'project') {
    // Этапы: без выбранного проекта — пустой список
    if (!parentVal) {
      items = [];
    } else {
      const projItem = (dirs['_ids_project'] || []).find((i) => i.value === parentVal);
      if (projItem) items = allItems.filter((i) => i.project_id === projItem.id);
      else items = [];
    }
    if (selectedVal && !items.find((i) => i.value === selectedVal)) {
      const ghost = document.createElement('option');
      ghost.value = selectedVal;
      ghost.textContent = selectedVal;
      ghost.selected = true;
      ghost.style.color = 'var(--muted)';
      sel.appendChild(ghost);
    }
  } else if (parentVal && parentDirKey) {
    const parentItem = (dirs[`_ids_${parentDirKey}`] || []).find((i) => i.value === parentVal);
    if (parentItem) items = allItems.filter((i) => i.parent_id === parentItem.id);
    // Фантомная опция для текущего значения из другого родителя
    if (selectedVal && !items.find((i) => i.value === selectedVal)) {
      const ghost = document.createElement('option');
      ghost.value = selectedVal;
      ghost.textContent = selectedVal;
      ghost.selected = true;
      ghost.style.color = 'var(--muted)';
      sel.appendChild(ghost);
    }
  }
  let found = false;
  items.forEach((item) => {
    const o = document.createElement('option');
    o.value = item.value;
    // Для этапов показываем label (номер + название) вместо голого номера
    o.textContent = item.label || item.value;
    if (item.value === selectedVal) {
      o.selected = true;
      found = true;
    }
    // Ограничения по роли: dept_head/dept_deputy/sector_head могут выбрать только свой отдел
    if (
      dirKey === 'dept' &&
      !IS_ADMIN &&
      USER_DEPT &&
      item.value !== USER_DEPT &&
      ['dept_head', 'dept_deputy', 'sector_head'].includes(USER_ROLE)
    ) {
      o.disabled = true;
      o.style.color = 'var(--muted)';
    }
    // sector_head может выбрать только свой сектор
    if (
      dirKey === 'sector' &&
      !IS_ADMIN &&
      USER_SECTOR &&
      item.value !== USER_SECTOR &&
      USER_ROLE === 'sector_head'
    ) {
      o.disabled = true;
      o.style.color = 'var(--muted)';
    }
    sel.appendChild(o);
  });
  if (selectedVal && !found) {
    const o = document.createElement('option');
    o.value = selectedVal;
    o.textContent = selectedVal;
    o.selected = true;
    sel.appendChild(o);
  }
}

// Создаёт или обновляет задачу: проверяет конфликты с отпуском, собирает данные, POST/PUT
async function submitNewTask() {
  const ds = document.getElementById('nt-date_start').value || null;
  const de = document.getElementById('nt-date_end').value || null;

  if (ds && de && newTaskExecutorsList.length > 0) {
    const checkRes = await fetch('/api/check_vacation_conflict/', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({
        executors: newTaskExecutorsList.map((e) => e.name),
        date_start: ds,
        date_end: de,
      }),
    });
    const checkData = checkRes.ok ? await checkRes.json() : {};
    const conflicts = checkData.conflicts || [];
    if (conflicts.length > 0) {
      const conflictMsg = conflicts
        .map((c) => `${c.executor}: отпуск с ${c.vacation_start} по ${c.vacation_end}`)
        .join('\n');
      const action = await showVacationConflictModal(conflictMsg);
      if (action === 'cancel') return;
      else if (action === 'adjust') {
        notify('Откорректируйте даты задачи', 'err');
        return;
      }
    }
  }

  let planHours = {};
  const keys = getTaskMonthKeys(ds, de);
  if (keys.length > 1) {
    document.querySelectorAll('#nt-plan-months-wrap input[data-month]').forEach((inp) => {
      const val = parseFloat(inp.value);
      if (!isNaN(val) && val > 0) planHours[inp.dataset.month] = val;
    });
  } else {
    const singleVal = parseFloat(document.getElementById('nt-plan_hours_single').value);
    if (keys.length === 1 && !isNaN(singleVal) && singleVal > 0) planHours[keys[0]] = singleVal;
  }

  // Проверка: распланированная трудоёмкость > плановой трудоёмкости из ПП
  const ppLabor = _editingTaskOriginal ? parseFloat(_editingTaskOriginal.pp_labor) : NaN;
  if (!isNaN(ppLabor) && ppLabor > 0) {
    const planned = Object.values(planHours).reduce((s, v) => s + (parseFloat(v) || 0), 0);
    if (planned > ppLabor) {
      const ok = await confirmDialog(
        `Распланированная трудоёмкость (${planned} ч) превышает плановую (${ppLabor} ч).\n\nПлановая трудоёмкость — значение из Производственного плана, рассчитанное по нормативам (листы А4 × норма × коэфф.).\n\nПродолжить сохранение?`,
        'Превышение трудоёмкости',
      );
      if (!ok) return;
    }
  }

  // Клиентская валидация обязательных полей
  const workNameVal = document.getElementById('nt-work_name').value.trim();
  if (!workNameVal) {
    notify('Укажите наименование работы', 'err');
    document.getElementById('nt-work_name').focus();
    return;
  }
  if (ds && de && ds > de) {
    notify('Дата начала не может быть позже даты окончания', 'err');
    document.getElementById('nt-date_start').focus();
    return;
  }

  const data = {
    task_type: pendingTaskType,
    dept: document.getElementById('nt-dept').value || null,
    sector: document.getElementById('nt-sector').value || null,
    project: document.getElementById('nt-project').value || null,
    stage: document.getElementById('nt-stage').value || null,
    executor: null,
    work_name: workNameVal || null,
    justification: document.getElementById('nt-justification').value || null,
    description: document.getElementById('nt-description')?.value || null,
    date_start: ds,
    date_end: de,
    deadline: document.getElementById('nt-deadline').value || null,
    plan_hours: planHours,
    actions: document.getElementById('nt-actions')?.value || null,
    executors_list: newTaskExecutorsList,
  };

  if (editingTaskId && _editingTaskOriginal) {
    data.actions = _editingTaskOriginal.actions || null;
    data.executor = _editingTaskOriginal.executor || null;
    // Оптимистичная блокировка: проверим, не изменил ли другой пользователь
    if (_editingTaskOriginal.updated_at) {
      data.updated_at = _editingTaskOriginal.updated_at;
    }
  }

  if (editingTaskId) {
    const res = await fetch(`/api/tasks/${editingTaskId}/`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify(data),
    });
    if (res.status === 409) {
      let msg = 'Задачу изменил другой пользователь. Перезагрузите данные и повторите правки.';
      try {
        const e = await res.json();
        if (e && e.message) msg = e.message;
      } catch (_) {
        /* ignored */
      }
      notify('⚠ ' + msg, 'err');
      return;
    }
    if (!res.ok) {
      let msg = 'Ошибка сохранения';
      try {
        const e = await res.json();
        msg = e.error || e.detail || Object.values(e).flat().join('; ') || msg;
      } catch (_) {
        /* ignored */
      }
      notify(msg, 'err');
      return;
    }
    closeNewTaskModal();
    await loadTasks();
    notify('✓ Изменения сохранены', 'ok');
  } else {
    const res = await fetch('/api/tasks/create/', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      let msg = 'Ошибка создания задачи';
      try {
        const e = await res.json();
        msg = e.error || e.detail || Object.values(e).flat().join('; ') || msg;
      } catch (_) {
        /* ignored */
      }
      notify(msg, 'err');
      return;
    }
    const resp = await res.json();
    _spPinnedRowId = resp.id || null;
    _spPinKeep = true;
    closeNewTaskModal();
    // Сбрасываем фильтры чтобы новая задача была видна (без лишнего renderTable)
    colFilters = {};
    document.querySelectorAll('.col-filter').forEach((inp) => {
      inp.value = '';
      inp.classList.remove('active');
      inp.nextElementSibling.classList.remove('visible');
    });
    Object.keys(mfSelections).forEach((k) => (mfSelections[k] = new Set()));
    document.querySelectorAll('.mf-trigger').forEach((btn) => {
      if (!btn.classList.contains('mf-icon')) btn.textContent = MF_DEFAULTS[btn.dataset.col] || '▼';
      btn.classList.remove('active');
    });
    if (activeMfDropdown) {
      activeMfDropdown.remove();
      activeMfDropdown = null;
      activeMfBtn = null;
    }
    document.getElementById('filtersActiveBadge').classList.remove('visible');
    spSelectedDepts = new Set();
    _saveSPDepts();
    if (_spDeptFilter) _spDeptFilter.refresh();
    await loadTasks();
    notify('✓ Задача создана', 'ok');
  }
}

// ── DIRS ──────────────────────────────────────────────────────────────────
async function loadDirs() {
  try {
    const res = await fetch('/api/directories/');
    if (!res.ok) {
      console.error('loadDirs HTTP', res.status);
      return;
    }
    const raw = await res.json();
    dirs = {};
    for (const [type, items] of Object.entries(raw)) {
      dirs[type] = Array.isArray(items) ? items.map((i) => i.value) : [];
      dirs[`_ids_${type}`] = items;
    }
    // Алиас: API возвращает секторы под ключом 'sector';
    // для совместимости с логикой фильтрации также пишем в 'sector_head'
    if (raw.sector) {
      dirs['sector_head'] = dirs['sector'];
      dirs['_ids_sector_head'] = dirs['_ids_sector'];
    }
  } catch (e) {
    console.error('loadDirs error:', e);
  }
}

// ── REPORT ────────────────────────────────────────────────────────────────
// Варианты нормоконтроля
const NORM_CONTROL_OPTIONS = ['штатный', '029'];
// Варианты ИИ/ПИ для корректировки
const II_PI_OPTIONS = ['ИИ', 'ПИ'];

// Определяет конфигурацию полей по типу задачи
// Возвращает { disabled: Set<field>, required: Set<field>, bvd_required: bool, is_correction: bool }
function _reportConfig(taskType) {
  const tt = (taskType || 'Выпуск нового документа').trim();
  let disabled = new Set();
  let required = new Set();
  let bvd_required = false;
  let is_correction = false;

  if (tt === 'Выпуск нового документа') {
    required = new Set([
      'doc_name',
      'doc_designation',
      'inventory_num',
      'date_accepted',
      'doc_type',
      'doc_class',
      'sheets_a4',
      'norm',
      'norm_control',
      'doc_link',
    ]);
  } else if (tt === 'Корректировка документа') {
    // Отдельная колонка ИИ/ПИ; наим. и обознач. из ЕТБД (редактируемые)
    // «Инвентарный №» → «Номер изв.» (редактируемое, через doc_number)
    // Вид, Класс, Коэфф, БВД — неактивны
    is_correction = true;
    disabled = new Set(['doc_type', 'doc_class', 'coeff', 'bvd_hours']);
    required = new Set([
      'ii_pi',
      'doc_name',
      'doc_designation',
      'doc_number',
      'date_accepted',
      'sheets_a4',
      'norm',
      'norm_control',
    ]);
  } else if (tt === 'Разработка') {
    disabled = new Set([
      'inventory_num',
      'date_accepted',
      'doc_type',
      'doc_class',
      'sheets_a4',
      'norm',
      'coeff',
      'norm_control',
    ]);
    bvd_required = true;
    required = new Set(['doc_name', 'doc_designation', 'bvd_hours']);
  } else if (tt === 'Сопровождение (ОКАН)') {
    disabled = new Set([
      'inventory_num',
      'date_accepted',
      'doc_type',
      'doc_class',
      'sheets_a4',
      'norm',
      'coeff',
      'doc_link',
    ]);
    bvd_required = true;
    required = new Set(['doc_name', 'doc_designation', 'bvd_hours']);
  }
  return { disabled, required, bvd_required, is_correction };
}

// Открывает модал отчётных документов для задачи.
// Принимает объект задачи или числовой ID.
// Загружает список отчётов из API, для writer создаёт пустую строку если нет данных.
async function openReportModal(taskOrId) {
  // Определяем задачу — из объекта или по ID
  if (typeof taskOrId === 'object' && taskOrId !== null) {
    currentTask = taskOrId;
    currentTaskId = taskOrId.id;
  } else {
    currentTaskId = taskOrId;
    currentTask = tasks.find((x) => x.id === taskOrId) || { id: taskOrId };
  }
  // Заголовок модала — наименование задачи
  document.getElementById('reportTaskRef').textContent =
    currentTask.work_name || `Задача #${currentTaskId}`;
  const res = await fetch(`/api/reports/${currentTaskId}/`);
  if (!res.ok) {
    notify('Ошибка загрузки отчётов', 'err');
    return;
  }
  reportRows = await res.json();
  // Проверка прав на редактирование отчётов этой задачи
  const canEditThisReport = _canModify(currentTask.dept, currentTask.sector);
  // Если отчётов нет — для writer своего отдела сразу одна пустая строка
  if (reportRows.length === 0 && canEditThisReport) {
    reportRows.push(_makeNewReportRow());
  }
  renderReportTable();
  // Кнопка «Добавить строку» — только для writer своего отдела
  const addRowBtn = document.getElementById('btnAddReportRow');
  if (addRowBtn) addRowBtn.style.display = canEditThisReport ? '' : 'none';
  document.getElementById('reportModal').classList.add('open');
  // Пересчитать высоту textarea после показа модала (scrollHeight=0 пока display:none)
  requestAnimationFrame(() => {
    var cells = [].slice.call(document.querySelectorAll('#reportBody .r-cell'));
    cells.forEach(function (c) {
      c.style.height = 'auto';
    });
    var heights = cells.map(function (c) {
      return c.scrollHeight;
    });
    cells.forEach(function (c, i) {
      c.style.height = heights[i] + 'px';
    });
  });
}

// Создаёт объект пустой строки отчёта с дефолтными полями
function _makeNewReportRow() {
  const row = { task_id: currentTaskId };
  // Норматив из ЕТБД
  if (currentTask && currentTask.norm != null && currentTask.norm !== '') {
    row.norm = currentTask.norm;
  }
  // Наименование и обозначение из ЕТБД для всех типов
  if (currentTask && currentTask.work_name) row.doc_name = currentTask.work_name;
  if (currentTask && currentTask.description) row.doc_designation = currentTask.description;
  return row;
}

function closeReportModal() {
  document.getElementById('reportModal').classList.remove('open');
  currentTaskId = null;
  currentTask = null;
}

// User menu — управляется base.html (toggleBaseUserMenu)

// Обновляет заголовки таблицы в зависимости от типа задачи
function _updateReportHeader(cfg) {
  // Колонка ИИ/ПИ — только для корректировки
  const thIiPi = document.getElementById('rh_ii_pi');
  if (thIiPi) thIiPi.style.display = cfg.is_correction ? '' : 'none';
  // «Инвентарный №» → «Номер изв.» для корректировки
  const thInv = document.getElementById('rh_inventory');
  if (thInv) thInv.textContent = cfg.is_correction ? 'Номер изв.' : 'Инвентарный №';
  // Колонка «Срок действия» — только для корректировки
  const thExp = document.getElementById('rh_date_expires');
  if (thExp) thExp.style.display = cfg.is_correction ? '' : 'none';
}

// Перерисовывает таблицу отчётов: обновляет заголовки и пересоздаёт строки
function renderReportTable() {
  const cfg = _reportConfig((currentTask && currentTask.task_type) || '');
  _updateReportHeader(cfg); // Настраиваем видимость колонок по типу задачи
  const tbody = document.getElementById('reportBody');
  tbody.innerHTML = ''; // Очищаем tbody перед перерисовкой
  reportRows.forEach((r, i) => tbody.appendChild(makeReportRow(r, i, cfg))); // Создаём строки заново
}

// Хелпер: создаёт <td> с <select> для строки отчёта
// field    — имя поля (data-field), options — массив вариантов,
// currentVal — текущее значение, isDisabled — блокировка ввода
function _makeSelectCell(field, options, currentVal, isDisabled) {
  const td = document.createElement('td');
  td.dataset.col = field;
  const sel = document.createElement('select');
  sel.className = 'r-cell r-cell-select';
  sel.dataset.field = field;
  // Пустой вариант «—» по умолчанию
  const emptyOpt = document.createElement('option');
  emptyOpt.value = '';
  emptyOpt.textContent = '—';
  sel.appendChild(emptyOpt);
  // Заполняем варианты; выбираем совпадающий
  options.forEach((opt) => {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = opt;
    if (currentVal === opt) o.selected = true;
    sel.appendChild(o);
  });
  // Блокируем поле если isDisabled (зависит от типа задачи/конфига)
  if (isDisabled) {
    sel.disabled = true;
    sel.classList.add('r-cell-disabled');
    td.classList.add('r-td-disabled');
  }
  td.appendChild(sel);
  return td;
}

// Хелпер: создаёт <td> с <textarea> для строки отчёта
// field — имя поля, value — начальное значение, isDisabled — блокировка
function _makeTextCell(field, value, isDisabled) {
  const td = document.createElement('td');
  td.dataset.col = field;
  const inp = document.createElement('textarea');
  inp.className = 'r-cell';
  inp.rows = 1;
  inp.value = value != null ? String(value) : ''; // null/undefined → пустая строка
  inp.dataset.field = field;
  // Авторесайз по мере ввода текста
  inp.addEventListener('input', () => {
    requestAnimationFrame(() => {
      inp.style.height = 'auto';
      inp.style.height = inp.scrollHeight + 'px';
    });
  });
  // Блокируем поле если isDisabled (зависит от типа задачи/конфига)
  if (isDisabled) {
    inp.disabled = true;
    inp.classList.add('r-cell-disabled');
    td.classList.add('r-td-disabled');
  }
  td.appendChild(inp);
  // Авторесайз при начальной загрузке (текст уже заполнен)
  requestAnimationFrame(() => {
    inp.style.height = 'auto';
    inp.style.height = inp.scrollHeight + 'px';
  });
  return td;
}

// Хелпер: создаёт <td> с <input type="date"> для строки отчёта
// field — имя поля, value — дата ISO (YYYY-MM-DD), isDisabled — блокировка
function _makeDateCell(field, value, isDisabled) {
  const td = document.createElement('td');
  td.dataset.col = field;
  const inp = document.createElement('input');
  inp.type = 'date';
  inp.className = 'r-cell r-cell-date';
  inp.dataset.field = field;
  inp.value = value || ''; // Пустая строка если дата не задана
  if (field === 'date_accepted') inp.max = new Date().toISOString().slice(0, 10);
  // Блокируем поле если isDisabled (зависит от типа задачи/конфига)
  if (isDisabled) {
    inp.disabled = true;
    inp.classList.add('r-cell-disabled');
    td.classList.add('r-td-disabled');
  }
  td.appendChild(inp);
  return td;
}

function makeReportRow(r, idx, cfg) {
  const tr = document.createElement('tr');
  tr.dataset.rid = r.id || '';

  // Колонка ИИ/ПИ — только для корректировки, первая
  if (cfg.is_correction) {
    const td = _makeSelectCell('ii_pi', II_PI_OPTIONS, r.ii_pi || '', false);
    td.style.display = '';
    // При смене ИИ/ПИ обновляем disabled у поля Срок действия в той же строке
    const sel = td.querySelector('select');
    if (sel)
      sel.addEventListener('change', function () {
        const expiresCell = tr.querySelector('[data-field="date_expires"]');
        if (!expiresCell) return;
        const isII = this.value === 'ИИ';
        expiresCell.disabled = isII;
        expiresCell.classList.toggle('r-cell-disabled', isII);
        expiresCell.closest('td').classList.toggle('r-td-disabled', isII);
        if (isII) expiresCell.value = '';
      });
    tr.appendChild(td);
  } else {
    // Пустая ячейка-заглушка чтобы colspan в thead работал правильно
    const td = document.createElement('td');
    td.style.display = 'none';
    tr.appendChild(td);
  }

  // Наименование и Обозначение — всегда текст (из ЕТБД, редактируемые)
  tr.appendChild(_makeTextCell('doc_name', r.doc_name, false));
  tr.appendChild(_makeTextCell('doc_designation', r.doc_designation, false));

  // Инвентарный № / Номер изв. (для корректировки — поле doc_number)
  if (cfg.is_correction) {
    tr.appendChild(_makeTextCell('doc_number', r.doc_number, false));
  } else {
    tr.appendChild(
      _makeTextCell('inventory_num', r.inventory_num, cfg.disabled.has('inventory_num')),
    );
  }

  // Дата выпуска
  tr.appendChild(
    _makeDateCell('date_accepted', r.date_accepted, cfg.disabled.has('date_accepted')),
  );

  // Срок действия — только для корректировки; disabled если ИИ/ПИ = «ИИ»
  if (cfg.is_correction) {
    const expiresDisabled = r.ii_pi === 'ИИ';
    tr.appendChild(_makeDateCell('date_expires', r.date_expires, expiresDisabled));
  } else {
    const td = document.createElement('td');
    td.style.display = 'none';
    tr.appendChild(td);
  }

  // Вид doc
  tr.appendChild(_makeTextCell('doc_type', r.doc_type, cfg.disabled.has('doc_type')));

  // Класс doc
  tr.appendChild(_makeTextCell('doc_class', r.doc_class, cfg.disabled.has('doc_class')));

  // Листов А4
  tr.appendChild(_makeTextCell('sheets_a4', r.sheets_a4, cfg.disabled.has('sheets_a4')));

  // Норматив
  tr.appendChild(_makeTextCell('norm', r.norm, cfg.disabled.has('norm')));

  // Коэфф
  tr.appendChild(_makeTextCell('coeff', r.coeff, cfg.disabled.has('coeff')));

  // БВД
  tr.appendChild(_makeTextCell('bvd_hours', r.bvd_hours, cfg.disabled.has('bvd_hours')));

  // Нормоконтроль
  tr.appendChild(
    _makeSelectCell(
      'norm_control',
      NORM_CONTROL_OPTIONS,
      r.norm_control || '',
      cfg.disabled.has('norm_control'),
    ),
  );

  // Ссылка
  tr.appendChild(_makeTextCell('doc_link', r.doc_link, cfg.disabled.has('doc_link')));

  // Дата заполнения отчёта (created_at) — read-only, только для отображения.
  // Для новых (несохранённых) строк — прочерк.
  const createdTd = document.createElement('td');
  createdTd.style.cssText = 'text-align:center;color:var(--muted);white-space:nowrap;';
  if (r.created_at) {
    const d = r.created_at.slice(0, 10).split('-'); // YYYY-MM-DD → DD.MM.YYYY
    createdTd.textContent = `${d[2]}.${d[1]}.${d[0]}`;
  } else {
    createdTd.textContent = '—';
  }
  tr.appendChild(createdTd);

  // Кнопки ✓ сохранить / ✕ удалить — только для writer своего отдела
  const actTd = document.createElement('td');
  actTd.style.cssText = 'padding:4px 6px;white-space:nowrap;';
  const _canEditReport = _canModify(currentTask?.dept, currentTask?.sector);

  if (_canEditReport) {
    const saveBtn = document.createElement('button');
    saveBtn.className = 'r-save';
    saveBtn.title = 'Сохранить строку';
    saveBtn.textContent = '✓';
    saveBtn.onclick = async () => {
      saveBtn.disabled = true;
      saveBtn.textContent = '…';
      const ok = await saveOneReportRow(tr, r, idx);
      if (ok) {
        saveBtn.textContent = '✓';
        saveBtn.disabled = false;
      } else {
        saveBtn.textContent = '✓';
        saveBtn.disabled = false;
      }
    };

    const delBtn = document.createElement('button');
    delBtn.className = 'r-del';
    delBtn.title = 'Удалить строку';
    delBtn.textContent = '✕';
    delBtn.onclick = async () => {
      if (
        !(await confirmDialog(
          'Удалить строку отчёта? Данные будут удалены из ЕТБД без возможности восстановления.',
        ))
      )
        return;
      if (r.id) {
        const delRes = await fetchJson(`/api/reports/${r.id}/detail/`, { method: 'DELETE' });
        if (delRes._error) return;
      }
      reportRows.splice(idx, 1);
      renderReportTable();
    };

    actTd.appendChild(saveBtn);
    actTd.appendChild(delBtn);
  }

  // Для role=user или чужого отдела: все поля read-only
  if (!_canEditReport) {
    tr.querySelectorAll('textarea, input, select').forEach((el) => {
      el.disabled = true;
    });
  }

  tr.appendChild(actTd);
  return tr;
}

function _syncRowsFromDom() {
  // Считываем текущие значения из DOM обратно в reportRows (сохраняем введённые данные)
  const trs = document.querySelectorAll('#reportBody tr');
  trs.forEach((tr, idx) => {
    if (!reportRows[idx]) return;
    tr.querySelectorAll('.r-cell').forEach((el) => {
      if (!el.disabled) reportRows[idx][el.dataset.field] = el.value || '';
    });
  });
}

// Добавляет пустую строку в таблицу отчётов (кнопка «＋ Добавить строку»)
function addReportRow() {
  _syncRowsFromDom(); // Сначала сохраняем введённые данные из DOM
  reportRows.push(_makeNewReportRow()); // Добавляем пустую строку в массив
  renderReportTable(); // Перерисовываем таблицу
}

// Сохраняет одну строку отчёта (кнопка ✓ в строке)
// tr — DOM-строка таблицы, r — объект из reportRows, idx — индекс в массиве
async function saveOneReportRow(tr, r, idx) {
  const cfg = _reportConfig((currentTask && currentTask.task_type) || '');
  const data = { task_id: currentTaskId }; // ID задачи-владельца
  // Собираем значения всех полей из DOM-элементов строки
  tr.querySelectorAll('.r-cell').forEach((el) => {
    data[el.dataset.field] = el.value || null;
  });

  const missing = Array.from(cfg.required).filter((f) => !data[f] || String(data[f]).trim() === '');
  if (cfg.bvd_required && (!data.bvd_hours || String(data.bvd_hours).trim() === ''))
    missing.push('bvd_hours');
  if (missing.length > 0) {
    notify('Заполните обязательные поля: ' + missing.join(', '), 'err');
    return false;
  }

  // Валидация URL в поле «Ссылка»
  if (data.doc_link && !/^https?:\/\/\S+/.test(data.doc_link.trim())) {
    notify('Поле «Ссылка» должно содержать URL (http:// или https://)', 'err');
    return false;
  }

  try {
    const rid = tr.dataset.rid || r.id;
    if (rid) {
      const updRes = await fetchJson(`/api/reports/${rid}/detail/`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
      if (updRes._error) return false;
    } else {
      let resp = await fetchJson('/api/reports/', { method: 'POST', body: JSON.stringify(data) });
      // Backend возвращает 409 если у задачи есть плановые часы в будущих
      // месяцах. Спрашиваем пользователя и, при согласии, отправляем
      // повторно с флагом confirm_zero_future=true.
      if (resp && resp._conflict && resp.error === 'confirm_zero_future_required') {
        const months = Array.isArray(resp.future_months) ? resp.future_months : [];
        const monthsTxt = months.length ? `\n\nБудущие месяцы с часами: ${months.join(', ')}` : '';
        const ok = window.confirm(
          'Задача имеет плановые часы в будущих месяцах.\n' +
            'При сохранении отчёта они будут обнулены (досрочное выполнение).' +
            monthsTxt +
            '\n\nПродолжить?',
        );
        if (!ok) {
          notify('Сохранение отчёта отменено', 'warn');
          return false;
        }
        resp = await fetchJson('/api/reports/', {
          method: 'POST',
          body: JSON.stringify({ ...data, confirm_zero_future: true }),
        });
      }
      if (resp._error || resp._conflict) return false;
      if (resp && resp.id) {
        tr.dataset.rid = resp.id;
        reportRows[idx].id = resp.id;
      }
    }
    // Визуальный фидбек: строка мигает зелёным
    tr.style.transition = 'background .2s';
    tr.style.background = 'var(--success-light, #dcfce7)';
    setTimeout(() => {
      tr.style.background = '';
    }, 1200);
    notify('✓ Строка сохранена', 'ok');

    // Автозаполнение ЖИ для ПИ
    if (data.ii_pi === 'ПИ' && currentTask) {
      await _syncNoticeFromReport(data, tr.dataset.rid || r.id);
    }

    return true;
  } catch (e) {
    notify('Ошибка сохранения: ' + e.message, 'err');
    return false;
  }
}

// Автоматически создаёт запись в ЖИ при сохранении строки отчёта с типом ПИ
// data — собранные поля строки, reportId — ID сохранённого отчёта
async function _syncNoticeFromReport(data, reportId) {
  // Берём текущую задачу для получения отдела
  const task = currentTask || {};
  const noticeData = {
    ii_pi: 'ПИ',
    notice_number: data.doc_number || '',
    subject: data.doc_name || '',
    doc_designation: data.doc_designation || '',
    date_issued: data.date_accepted || '',
    date_expires: data.date_expires || '',
    dept: task.dept || '',
    status: 'active',
  };
  try {
    if (noticeData.notice_number) {
      // Проверяем дубликат через серверный фильтр (вместо загрузки всего журнала)
      const check = await fetchJson(
        `/api/journal/?check_number=${encodeURIComponent(noticeData.notice_number)}&check_ii_pi=${encodeURIComponent('ПИ')}`,
      );
      if (!check._error && !check.exists) {
        await fetchJson('/api/journal/create/', {
          method: 'POST',
          body: JSON.stringify(noticeData),
        });
      }
    }
  } catch (e) {
    // Не критично — просто логируем
    console.warn('ЖИ автозаполнение:', e.message);
  }
}

// Сохраняет все строки отчёта разом (кнопка «Сохранить всё» в модале)
async function saveAllReports() {
  const cfg = _reportConfig((currentTask && currentTask.task_type) || '');
  const trs = Array.from(document.querySelectorAll('#reportBody tr')); // Все строки таблицы
  for (const tr of trs) {
    const rid = tr.dataset.rid; // ID записи (пустой для новых)
    const data = { task_id: currentTaskId }; // ID задачи-владельца
    // Собираем значения полей из DOM
    tr.querySelectorAll('.r-cell').forEach((el) => {
      data[el.dataset.field] = el.value || null;
    });

    // Обязательные поля с учётом типа задачи
    const missing = Array.from(cfg.required).filter((f) => {
      const v = data[f];
      return !v || String(v).trim() === '';
    });
    if (cfg.bvd_required && (!data.bvd_hours || String(data.bvd_hours).trim() === '')) {
      missing.push('bvd_hours');
    }
    if (missing.length > 0) {
      notify('Заполните обязательные поля: ' + missing.join(', '), 'err');
      return;
    }

    if (rid) {
      const updRes = await fetchJson(`/api/reports/${rid}/detail/`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
      if (updRes._error) return;
    } else {
      let resp = await fetchJson('/api/reports/', { method: 'POST', body: JSON.stringify(data) });
      // Досрочное выполнение: подтверждение обнуления часов в будущих месяцах
      if (resp && resp._conflict && resp.error === 'confirm_zero_future_required') {
        const months = Array.isArray(resp.future_months) ? resp.future_months : [];
        const monthsTxt = months.length ? `\n\nБудущие месяцы с часами: ${months.join(', ')}` : '';
        const ok = window.confirm(
          'Задача имеет плановые часы в будущих месяцах.\n' +
            'При сохранении отчёта они будут обнулены (досрочное выполнение).' +
            monthsTxt +
            '\n\nПродолжить?',
        );
        if (!ok) {
          notify('Сохранение отчёта отменено', 'warn');
          return;
        }
        resp = await fetchJson('/api/reports/', {
          method: 'POST',
          body: JSON.stringify({ ...data, confirm_zero_future: true }),
        });
      }
      if (resp._error || resp._conflict) return;
      if (resp && resp.id) tr.dataset.rid = resp.id;
    }
  }
  notify('✓ Отчёт сохранён', 'ok');
}

// ── USERS — управление пользователями (admin-only модал) ──────────────────
// Открывает модал со списком пользователей; загружает данные с /api/users/
async function openUsersModal() {
  let users;
  try {
    const res = await fetch('/api/users/');
    users = res.ok ? await res.json() : [];
  } catch (e) {
    notify('Ошибка загрузки пользователей: ' + e.message, 'err');
    return;
  }
  // Рендерим таблицу: заголовок + строка на каждого пользователя
  const tbl = document.getElementById('usersTable');
  tbl.innerHTML = "<tr><th>Логин</th><th>Роль</th><th style='text-align:right'>Действия</th></tr>";
  users.forEach((u) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${escapeHtml(u.username)}</td><td>${escapeHtml(u.role)}</td><td style="text-align:right">
      <button class="btn-reset-pw" data-uid="${u.id}" data-uname="${escapeHtml(u.username)}" title="Сбросить пароль">🔑 Пароль</button>
      <button class="btn-del" data-uid="${u.id}" title="Удалить">✕</button>
    </td>`;
    // Привязываем обработчики к кнопкам сброса пароля и удаления
    tr.querySelector('.btn-reset-pw').addEventListener('click', function () {
      resetUserPassword(u.id, u.username);
    });
    tr.querySelector('.btn-del').addEventListener('click', function () {
      delUser(u.id);
    });
    tbl.appendChild(tr);
  });
  document.getElementById('usersModal').classList.add('open');
}

// Создаёт нового пользователя (POST /api/users/)
async function createUser() {
  const username = document.getElementById('newUser').value.trim();
  const password = document.getElementById('newPass').value;
  const role = document.getElementById('newRole').value;
  if (!username || !password) return notify('Введите логин и пароль', 'err');
  const res = await fetch('/api/users/', {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ username, password, role }),
  });
  const data = await res.json();
  if (data.error) return notify(data.error, 'err');
  notify('✓ Пользователь создан', 'ok');
  openUsersModal(); // Перезагружаем таблицу
}

// Удаляет пользователя (DELETE /api/users/<id>/) с подтверждением
async function delUser(id) {
  if (!(await confirmDialog('Удалить пользователя?', 'Удаление пользователя'))) return;
  const resp = await fetch(`/api/users/${id}/`, { method: 'DELETE', headers: apiHeaders() });
  if (!resp.ok) {
    let errMsg = 'Ошибка удаления пользователя';
    try {
      const d = await resp.json();
      if (d && d.error) errMsg = d.error;
    } catch (_) {
      /* ignored */
    }
    showToast(errMsg, 'error');
    return;
  }
  openUsersModal(); // Перезагружаем таблицу
}

// Удаляет ВСЕ задачи из БД (admin-only, debug) с подтверждением
async function deleteAllTasks() {
  if (
    !(await confirmDialog(
      'Удалить ВСЕ задачи из базы данных? Это действие необратимо.',
      'Очистить задачи',
    ))
  )
    return;
  try {
    const res = await fetch('/api/tasks/all/', { method: 'DELETE', headers: apiHeaders() });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    notify('Все задачи удалены', 'ok');
    await loadTasks(); // Перерисовываем таблицу
  } catch (e) {
    notify('Ошибка удаления: ' + e.message, 'err');
  }
}

// Сбрасывает пароль пользователя (PUT /api/users/<uid>/password/)
async function resetUserPassword(uid, username) {
  const newPw = prompt(`Новый пароль для пользователя "${username}":`, '');
  if (newPw === null) return; // Отмена диалога
  if (newPw.length < 4) {
    notify('Пароль слишком короткий (мин. 4 символа)', 'err');
    return;
  }
  const res = await fetch(`/api/users/${uid}/password/`, {
    method: 'PUT',
    headers: apiHeaders(),
    body: JSON.stringify({ password: newPw }),
  });
  if (res.ok) {
    notify(`✓ Пароль пользователя "${username}" сброшен.`, 'ok');
  } else {
    const err = await res.json().catch(() => ({}));
    notify('Ошибка: ' + (err.error || res.status), 'err');
  }
}

// ── COL RESIZE — изменение ширины колонок перетаскиванием ──────────────────
// Все операции с шириной делегированы общему модулю window.ColResize
// (static/js/col_resize.js). Модуль хранит данные в `col_settings` под
// префиксом `plan_*`, чтобы не конфликтовать с настройками других таблиц.

// Инициализирует drag-обработчики. Вызывается один раз при старте страницы.
function initColResize() {
  const table = document.getElementById('mainTable');
  if (!table || !window.ColResize) return;
  window.ColResize.attach(table, {
    // После каждого пикселя ресайза пересчитываем textarea открытой задачи
    onResize: () => {
      const body = document.getElementById('taskBody');
      if (body) _resizeTextareas(body);
    },
  });
}

// Применяет сохранённые ширины колонок из colSettings (загружены с сервера).
// Поддерживает «старый» формат ключей без префикса — для обратной совместимости
// со старыми сохранениями у пользователей (новые ресайзы пишутся уже с префиксом).
function applyColSettings() {
  const table = document.getElementById('mainTable');
  if (!table) return;
  // Минимальные ширины для ПП-дат (узкие даты плохо читаются)
  const DATE_COLS_MIN = { ppds: 150, ppde: 160 };
  // Собираем «приведённый» объект: если ширина лежит под голым ключом —
  // копируем её под ключ с префиксом, чтобы модуль её нашёл.
  const src = colSettings || {};
  const resolved = { ...src };
  for (const k of Object.keys(src)) {
    if (!k.startsWith('plan_') && src[k] && src[k].width) {
      resolved['plan_' + k] = src[k];
    }
  }
  if (window.ColResize) window.ColResize.apply(table, resolved);
  // Минимумы для дат — ставим на th, если пользователь ещё не задал ширину
  for (const [key, minW] of Object.entries(DATE_COLS_MIN)) {
    const th = document.getElementById(`th-${key}`);
    if (!th) continue;
    const saved = resolved['plan_' + key] || src[key];
    if (!saved || !saved.width) th.style.minWidth = minW + 'px';
  }
}

// Обёртка для уведомлений: переводит short-коды (ok/err/info) в формат showToast
function notify(msg, type = 'ok') {
  const map = { ok: 'success', err: 'error', info: 'info' };
  showToast(msg, map[type] || 'info');
}

// ── DATE CHANGE MODAL ─────────────────────────────────────────────────────
let dateChangeCallback = null;
let dateChangeTaskId = null;
let dateChangeRow = null;

function showDateChangeModal(monthsCount, callback, taskId, row) {
  const modal = document.getElementById('dateChangeModal');
  const message = document.getElementById('dateChangeMessage');
  const monthWord = monthsCount === 1 ? 'месяц' : monthsCount < 5 ? 'месяца' : 'месяцев';
  message.textContent = `Изменение периода добавит ${monthsCount} новый ${monthWord}. Часы для исполнителей в новых месяцах нужно заполнить вручную.`;
  dateChangeCallback = callback;
  dateChangeTaskId = taskId;
  dateChangeRow = row;
  modal.classList.add('open');
}
function closeDateChangeModal() {
  document.getElementById('dateChangeModal').classList.remove('open');
  dateChangeCallback = null;
  dateChangeTaskId = null;
  dateChangeRow = null;
}
function cancelDateChange() {
  if (dateChangeCallback) dateChangeCallback(false);
  closeDateChangeModal();
}
async function fillLaterDateChange() {
  if (dateChangeTaskId && dateChangeRow) {
    await saveTask(dateChangeTaskId, dateChangeRow);
    await loadTasks();
    notify('Даты изменены. Заполните часы позже через редактирование', 'ok');
  }
  closeDateChangeModal();
}
function confirmDateChange() {
  if (dateChangeCallback) dateChangeCallback(true);
  closeDateChangeModal();
}

// ── VACATION CONFLICT MODAL ───────────────────────────────────────────────
let vacationConflictResolve = null;
function showVacationConflictModal(message) {
  return new Promise((resolve) => {
    vacationConflictResolve = resolve;
    document.getElementById('vacationConflictMessage').textContent = message;
    document.getElementById('vacationConflictModal').classList.add('open');
  });
}
function closeVacationConflictModal(action) {
  document.getElementById('vacationConflictModal').classList.remove('open');
  if (vacationConflictResolve) {
    vacationConflictResolve(action);
    vacationConflictResolve = null;
  }
}

// ── NEW TASK EXECUTORS MANAGEMENT — управление исполнителями при создании новой задачи ──
// Добавляет выбранного сотрудника в список исполнителей новой задачи
function addExecutorToNewTask() {
  const select = document.getElementById('nt-executor-select');
  const executorName = select.value;
  if (!executorName) {
    notify('Выберите сотрудника', 'err');
    return;
  }
  if (newTaskExecutorsList.find((e) => e.name === executorName)) {
    notify('Этот сотрудник уже добавлен', 'err');
    return;
  }
  newTaskExecutorsList.push({ name: executorName, hours: {} });
  renderNewTaskExecutorsList();
  select.value = '';
  notify('Исполнитель добавлен', 'ok');
}
// Удаляет исполнителя из списка новой задачи по индексу (с подтверждением)
async function removeExecutorFromNewTask(index) {
  if (!(await confirmDialog('Удалить исполнителя?', 'Удаление'))) return;
  newTaskExecutorsList.splice(index, 1);
  renderNewTaskExecutorsList();
  notify('Исполнитель удалён', 'ok');
}
// Перерисовывает список исполнителей новой задачи (бейджи + поля часов по месяцам)
function renderNewTaskExecutorsList() {
  const container = document.getElementById('nt-executors-list');
  if (newTaskExecutorsList.length === 0) {
    container.innerHTML =
      '<div style="text-align:center;color:var(--muted);padding:10px;font-size:16px;">Исполнители не добавлены</div>';
    return;
  }
  container.innerHTML = '';
  const ds = document.getElementById('nt-date_start').value || null;
  const de = document.getElementById('nt-date_end').value || null;
  const monthKeys = ds && de ? getTaskMonthKeys(ds, de) : [];

  newTaskExecutorsList.forEach((executor, index) => {
    const item = document.createElement('div');
    item.className = 'nt-executor-item';
    item.style.cssText =
      'background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:6px 10px;';
    let hoursHTML = '';
    if (monthKeys.length > 0) {
      hoursHTML = '<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:6px;">';
      monthKeys.forEach((key) => {
        const [year, month] = key.split('-');
        const monthName = MONTH_NAMES[parseInt(month)];
        const value = executor.hours[key] || '';
        hoursHTML += `
          <div style="display:flex;align-items:center;gap:4px;">
            <span style="font-size:12px;color:var(--muted);white-space:nowrap;">${monthName} ${year}:</span>
            <input type="number" class="form-input"
                   style="padding:3px 5px;font-size:13px;text-align:center;width:60px;"
                   data-exec-index="${index}" data-month="${key}"
                   value="${value}" min="0" step="0.5" placeholder="0"
                   onchange="updateNewTaskExecutorHours(${index}, '${key}', this.value)">
            <span style="font-size:12px;color:var(--muted);">ч</span>
          </div>`;
      });
      hoursHTML += '</div>';
    }
    item.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
        <div style="font-size:14px;font-weight:600;color:var(--text);">${escapeHtml(executor.name)}</div>
        <button class="nt-executor-remove" type="button" onclick="removeExecutorFromNewTask(${index})" title="Удалить исполнителя" style="padding:2px 7px;font-size:13px;">✕</button>
      </div>
      ${hoursHTML}`;
    container.appendChild(item);
  });
  updateTotalHours();
}
// Обновляет часы исполнителя в новой задаче при изменении input поля
function updateNewTaskExecutorHours(index, monthKey, value) {
  if (!newTaskExecutorsList[index]) return;
  const numValue = parseFloat(value);
  if (!value || value === '' || isNaN(numValue) || numValue <= 0) {
    delete newTaskExecutorsList[index].hours[monthKey];
  } else {
    newTaskExecutorsList[index].hours[monthKey] = numValue;
  }
  updateTotalHours();
}

// ── EXECUTORS MANAGEMENT — модал управления исполнителями существующей задачи ──
let currentTaskForExecutors = null; // ID задачи, для которой открыт модал
let taskExecutorsData = []; // Массив исполнителей текущей задачи

// Открывает модал исполнителей: загружает данные с сервера, рисует список
async function openExecutorsModal(taskId, taskName) {
  currentTaskForExecutors = taskId;
  document.getElementById('executorsTaskRef').textContent = `Задача: ${taskName}`;
  try {
    const res = await fetch(`/api/tasks/${taskId}/executors/`);
    taskExecutorsData = res.ok ? await res.json() : [];
  } catch (e) {
    notify('Ошибка загрузки исполнителей: ' + e.message, 'err');
    taskExecutorsData = [];
  }
  renderExecutorsList();
  document.getElementById('executorsModal').classList.add('open');
}
// Закрывает модал исполнителей и очищает данные
function closeExecutorsModal() {
  document.getElementById('executorsModal').classList.remove('open');
  currentTaskForExecutors = null;
  taskExecutorsData = [];
}
// Перерисовывает список исполнителей в модале (имя + поля часов по месяцам)
function renderExecutorsList() {
  const container = document.getElementById('executorsList');
  if (taskExecutorsData.length === 0) {
    container.innerHTML =
      '<div style="text-align:center;color:var(--muted);padding:20px;">Исполнители не добавлены</div>';
    return;
  }
  container.innerHTML = '';
  taskExecutorsData.forEach((executor, index) => {
    const item = document.createElement('div');
    item.className = 'executor-item';
    const months = getMonthsForTask();
    let monthsHTML = '';
    months.forEach((month) => {
      const value = executor.hours[month.key] || '';
      monthsHTML += `
        <div class="executor-month">
          <div class="executor-month-label">${month.label}</div>
          <input type="number" class="executor-month-input"
                 data-exec-index="${index}" data-month="${month.key}"
                 value="${value}" min="0" step="0.5" placeholder="0"
                 onchange="updateExecutorHours(${index}, '${month.key}', this.value)">
        </div>`;
    });
    item.innerHTML = `
      <div class="executor-item-header">
        <div class="executor-name">${escapeHtml(executor.name)}</div>
        <button class="executor-remove" onclick="removeExecutor(${index})" title="Удалить исполнителя">✕ Удалить</button>
      </div>
      <div class="executor-hours">${monthsHTML}</div>`;
    container.appendChild(item);
  });
}
// Возвращает массив последних 12 месяцев (ключ YYYY-MM + подпись) для полей часов
function getMonthsForTask() {
  const months = [];
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const label = d.toLocaleDateString('ru-RU', { month: 'short', year: '2-digit' });
    months.push({ key, label });
  }
  return months;
}
// Добавляет выбранного сотрудника в список исполнителей (модал существующей задачи)
function addExecutorToTask() {
  const select = document.getElementById('newExecutorSelect');
  const executorName = select.value;
  if (!executorName) {
    notify('Выберите сотрудника', 'err');
    return;
  }
  if (taskExecutorsData.find((e) => e.name === executorName)) {
    notify('Этот сотрудник уже добавлен', 'err');
    return;
  }
  taskExecutorsData.push({ name: executorName, hours: {} });
  renderExecutorsList();
  select.value = '';
  notify('Исполнитель добавлен', 'ok');
}
// Удаляет исполнителя из задачи по индексу (с подтверждением)
async function removeExecutor(index) {
  if (!(await confirmDialog('Удалить исполнителя из этой задачи?', 'Удаление'))) return;
  taskExecutorsData.splice(index, 1);
  renderExecutorsList();
  notify('Исполнитель удалён', 'ok');
}
// Обновляет часы исполнителя существующей задачи при изменении input поля
function updateExecutorHours(index, monthKey, value) {
  if (!taskExecutorsData[index]) return;
  const numValue = parseFloat(value);
  if (isNaN(numValue) || numValue < 0) taskExecutorsData[index].hours[monthKey] = 0;
  else taskExecutorsData[index].hours[monthKey] = numValue;
}
// Сохраняет список исполнителей задачи на сервер (PUT /api/tasks/<id>/)
async function saveTaskExecutors() {
  if (!currentTaskForExecutors) return;
  try {
    const res = await fetch(`/api/tasks/${currentTaskForExecutors}/`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify({ executors_list: taskExecutorsData }),
    });
    if (res.ok) {
      notify('✓ Исполнители сохранены', 'ok');
      closeExecutorsModal();
      await loadTasks();
    } else notify('Ошибка сохранения', 'err');
  } catch (error) {
    console.error('Error saving executors:', error);
    notify('Ошибка сохранения', 'err');
  }
}

// ── DEPENDENCIES — модал управления зависимостями между задачами ──────────
let currentDepsTaskId = null; // ID задачи, для которой открыт модал
let currentDepsTask = null; // Объект задачи целиком

// Открывает модал зависимостей: заголовок, даты, формы добавления (только writer)
function openDepsModal(t) {
  currentDepsTaskId = t.id;
  currentDepsTask = t;
  const modal = document.getElementById('depsModal');
  document.getElementById('depsModalTitle').textContent =
    `Зависимости: ${t.work_name || t.work_num || '#' + t.id}`;
  const ds = t.date_start ? t.date_start.split('-').reverse().join('.') : '—';
  const de = t.date_end ? t.date_end.split('-').reverse().join('.') : '—';
  document.getElementById('depsModalDates').textContent = `Сроки: ${ds} → ${de}`;
  if (IS_WRITER) {
    document.getElementById('depsAddForm').style.display = '';
    document.getElementById('depsAddSuccForm').style.display = '';
    _populateDepsSelect(t.id);
    _populateSuccSelect(t.id);
  } else {
    document.getElementById('depsAddForm').style.display = 'none';
    document.getElementById('depsAddSuccForm').style.display = 'none';
  }
  modal.classList.add('open');
  loadDeps(t.id);
}

// Закрывает модал зависимостей и очищает данные
function closeDepsModal() {
  document.getElementById('depsModal').classList.remove('open');
  currentDepsTaskId = null;
  currentDepsTask = null;
}

// Загружает предшественников и последователей для задачи, рисует таблицы + баннер конфликтов
async function loadDeps(taskId) {
  try {
    const res = await fetch(`/api/tasks/${taskId}/dependencies/`, { headers: apiHeaders() });
    if (!res.ok) {
      notify('Ошибка загрузки зависимостей', 'err');
      return;
    }
    const data = await res.json();
    renderPredecessors(data.predecessors || []);
    renderSuccessors(data.successors || []);
    const alignBar = document.getElementById('depsAlignBar');
    const txt = document.getElementById('depsAlignText');
    const predBtn = document.getElementById('depsAlignPredBtn');
    const succBtn = document.getElementById('depsAlignSuccBtn');
    const hasDeps = (data.predecessors || []).length > 0 || (data.successors || []).length > 0;
    if (data.has_conflict && IS_WRITER) {
      alignBar.style.display = '';
      txt.textContent = '⚠ Обнаружен конфликт сроков';
      txt.style.color = 'var(--danger, #e53e3e)';
      predBtn.style.display = data.has_pred_conflict ? '' : 'none';
      succBtn.style.display = data.has_succ_conflict ? '' : 'none';
    } else if (hasDeps) {
      alignBar.style.display = '';
      txt.textContent = '✓ Даты соответствуют зависимостям';
      txt.style.color = 'var(--success)';
      predBtn.style.display = 'none';
      succBtn.style.display = 'none';
    } else {
      alignBar.style.display = 'none';
    }
  } catch (e) {
    console.error('loadDeps error:', e);
    notify('Ошибка загрузки зависимостей', 'err');
  }
}

// Рисует таблицу предшественников (задача, тип связи, лаг, даты, кнопка удаления)
function renderPredecessors(preds) {
  const wrap = document.getElementById('depsPredBody');
  document.getElementById('depsPredCount').textContent = preds.length ? `(${preds.length})` : '';
  if (preds.length === 0) {
    wrap.innerHTML =
      '<div style="color:var(--muted);font-size:14px;padding:8px 0;">Нет предшественников</div>';
    return;
  }
  let html =
    '<table class="deps-table"><thead><tr><th>Задача</th><th>Тип</th><th>Лаг</th><th>Даты</th>';
  if (IS_WRITER) html += '<th style="width:40px;"></th>';
  html += '</tr></thead><tbody>';
  preds.forEach((d) => {
    const rowStyle = d.conflict ? 'background:rgba(229,62,62,0.08);' : '';
    html += `<tr data-dep-id="${d.id}" style="${rowStyle}">`;
    html += `<td>${escapeHtml(d.work_name || d.work_num || '#' + d.work_id)}</td>`;
    html += `<td><span class="dep-type-badge">${d.dep_type}</span></td>`;
    html += `<td style="font-family:var(--mono);">${d.lag_days}д</td>`;
    const ds = d.date_start ? d.date_start.split('-').reverse().join('.') : '—';
    const de = d.date_end ? d.date_end.split('-').reverse().join('.') : '—';
    const dateColor = d.conflict
      ? 'color:var(--danger, #e53e3e);font-weight:600;'
      : 'color:var(--text2);';
    html += `<td style="font-size:13px;${dateColor}">${ds} → ${de}${d.conflict ? ' ⚠' : ''}</td>`;
    if (IS_WRITER) {
      html += `<td><button class="btn-del" onclick="deleteDep(${d.id})" title="Удалить связь">✕</button></td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

// Рисует таблицу последователей (задача, тип связи, лаг, даты, кнопка удаления)
function renderSuccessors(succs) {
  const wrap = document.getElementById('depsSuccBody');
  document.getElementById('depsSuccCount').textContent = succs.length ? `(${succs.length})` : '';
  if (succs.length === 0) {
    wrap.innerHTML =
      '<div style="color:var(--muted);font-size:14px;padding:8px 0;">Нет последователей</div>';
    return;
  }
  let html =
    '<table class="deps-table"><thead><tr><th>Задача</th><th>Тип</th><th>Лаг</th><th>Даты</th>';
  if (IS_WRITER) html += '<th style="width:40px;"></th>';
  html += '</tr></thead><tbody>';
  succs.forEach((d) => {
    const rowStyle = d.conflict ? 'background:rgba(229,62,62,0.08);' : '';
    html += `<tr style="${rowStyle}">`;
    html += `<td>${escapeHtml(d.work_name || d.work_num || '#' + d.work_id)}</td>`;
    html += `<td><span class="dep-type-badge">${d.dep_type}</span></td>`;
    html += `<td style="font-family:var(--mono);">${d.lag_days}д</td>`;
    const ds = d.date_start ? d.date_start.split('-').reverse().join('.') : '—';
    const de = d.date_end ? d.date_end.split('-').reverse().join('.') : '—';
    const dateColor = d.conflict
      ? 'color:var(--danger, #e53e3e);font-weight:600;'
      : 'color:var(--text2);';
    html += `<td style="font-size:13px;${dateColor}">${ds} → ${de}${d.conflict ? ' ⚠' : ''}</td>`;
    if (IS_WRITER) {
      html += `<td><button class="btn-del" onclick="deleteDep(${d.id})" title="Удалить связь">✕</button></td>`;
    }
    html += '</tr>';
  });
  html += '</tbody></table>';
  wrap.innerHTML = html;
}

/* ── Searchable predecessor dropdown — поисковый дропдаун предшественников ── */
let _depsDropdownItems = []; // Все доступные задачи для выбора
let _depsDropdownHighlight = -1; // Индекс подсвеченного элемента (клавиатурная навигация)

// Заполняет массив элементов дропдауна (исключая текущую задачу)
function _populateDepsSelect(excludeId) {
  const input = document.getElementById('depsAddPredInput');
  const hidden = document.getElementById('depsAddPredSelect');
  input.value = '';
  hidden.value = '';
  _depsDropdownItems = [];
  tasks.forEach((t) => {
    if (t.id === excludeId) return;
    const name = t.work_name || t.work_num || '#' + t.id;
    const dept = t.dept ? ` [${t.dept}]` : '';
    _depsDropdownItems.push({ id: t.id, label: name + dept });
  });
  _renderDepsDropdownList('');
}

// Рисует отфильтрованный список в дропдауне предшественников
function _renderDepsDropdownList(filter) {
  const list = document.getElementById('depsAddPredList');
  const lc = filter.toLowerCase();
  const filtered = lc
    ? _depsDropdownItems.filter((it) => it.label.toLowerCase().includes(lc))
    : _depsDropdownItems;
  const selectedId = document.getElementById('depsAddPredSelect').value;
  if (filtered.length === 0) {
    list.innerHTML = '<div class="search-dropdown-empty">Ничего не найдено</div>';
  } else {
    list.innerHTML = filtered
      .map(
        (it) =>
          `<div class="search-dropdown-item${it.id == selectedId ? ' selected' : ''}" data-value="${it.id}">${escapeHtml(it.label)}</div>`,
      )
      .join('');
  }
  _depsDropdownHighlight = -1;
}

// IIFE: инициализация поискового дропдауна предшественников (focus, input, keydown, click)
(function initDepsDropdown() {
  document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('depsAddPredInput');
    const list = document.getElementById('depsAddPredList');
    const hidden = document.getElementById('depsAddPredSelect');
    if (!input) return;

    // Показать список при фокусе и при вводе текста
    input.addEventListener('focus', () => {
      _renderDepsDropdownList(input.value);
      list.classList.add('open');
    });
    input.addEventListener('input', () => {
      _renderDepsDropdownList(input.value);
      list.classList.add('open');
    });

    input.addEventListener('keydown', (e) => {
      const items = list.querySelectorAll('.search-dropdown-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _depsDropdownHighlight = Math.min(_depsDropdownHighlight + 1, items.length - 1);
        _highlightDepsItem(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _depsDropdownHighlight = Math.max(_depsDropdownHighlight - 1, 0);
        _highlightDepsItem(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (_depsDropdownHighlight >= 0 && items[_depsDropdownHighlight])
          items[_depsDropdownHighlight].click();
      } else if (e.key === 'Escape') {
        list.classList.remove('open');
      }
    });

    list.addEventListener('click', (e) => {
      const item = e.target.closest('.search-dropdown-item');
      if (!item) return;
      hidden.value = item.dataset.value;
      input.value = item.textContent;
      list.classList.remove('open');
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (!e.target.closest('#depsAddPredDropdown')) list.classList.remove('open');
    });
  });
})();

// Подсвечивает текущий элемент в дропдауне предшественников (навигация стрелками)
function _highlightDepsItem(items) {
  items.forEach((it, i) => it.classList.toggle('highlighted', i === _depsDropdownHighlight));
  if (items[_depsDropdownHighlight])
    items[_depsDropdownHighlight].scrollIntoView({ block: 'nearest' });
}

/* ── Searchable successor dropdown — поисковый дропдаун последователей ──── */
let _succDropdownItems = []; // Все доступные задачи для выбора
let _succDropdownHighlight = -1; // Индекс подсвеченного элемента

// Заполняет массив элементов дропдауна последователей (исключая текущую задачу)
function _populateSuccSelect(excludeId) {
  const input = document.getElementById('depsAddSuccInput');
  const hidden = document.getElementById('depsAddSuccSelect');
  input.value = '';
  hidden.value = '';
  _succDropdownItems = [];
  tasks.forEach((t) => {
    if (t.id === excludeId) return;
    const name = t.work_name || t.work_num || '#' + t.id;
    const dept = t.dept ? ` [${t.dept}]` : '';
    _succDropdownItems.push({ id: t.id, label: name + dept });
  });
  _renderSuccDropdownList('');
}

// Рисует отфильтрованный список в дропдауне последователей
function _renderSuccDropdownList(filter) {
  const list = document.getElementById('depsAddSuccList');
  const lc = filter.toLowerCase();
  const filtered = lc
    ? _succDropdownItems.filter((it) => it.label.toLowerCase().includes(lc))
    : _succDropdownItems;
  const selectedId = document.getElementById('depsAddSuccSelect').value;
  if (filtered.length === 0) {
    list.innerHTML = '<div class="search-dropdown-empty">Ничего не найдено</div>';
  } else {
    list.innerHTML = filtered
      .map(
        (it) =>
          `<div class="search-dropdown-item${it.id == selectedId ? ' selected' : ''}" data-value="${it.id}">${escapeHtml(it.label)}</div>`,
      )
      .join('');
  }
  _succDropdownHighlight = -1;
}

// Подсвечивает текущий элемент в дропдауне последователей (навигация стрелками)
function _highlightSuccItem(items) {
  items.forEach((it, i) => it.classList.toggle('highlighted', i === _succDropdownHighlight));
  if (items[_succDropdownHighlight])
    items[_succDropdownHighlight].scrollIntoView({ block: 'nearest' });
}

// IIFE: инициализация поискового дропдауна последователей
(function initSuccDropdown() {
  document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('depsAddSuccInput');
    const list = document.getElementById('depsAddSuccList');
    const hidden = document.getElementById('depsAddSuccSelect');
    if (!input) return;

    input.addEventListener('focus', () => {
      _renderSuccDropdownList(input.value);
      list.classList.add('open');
    });
    input.addEventListener('input', () => {
      _renderSuccDropdownList(input.value);
      list.classList.add('open');
    });

    input.addEventListener('keydown', (e) => {
      const items = list.querySelectorAll('.search-dropdown-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        _succDropdownHighlight = Math.min(_succDropdownHighlight + 1, items.length - 1);
        _highlightSuccItem(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _succDropdownHighlight = Math.max(_succDropdownHighlight - 1, 0);
        _highlightSuccItem(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (_succDropdownHighlight >= 0 && items[_succDropdownHighlight])
          items[_succDropdownHighlight].click();
      } else if (e.key === 'Escape') {
        list.classList.remove('open');
      }
    });

    list.addEventListener('click', (e) => {
      const item = e.target.closest('.search-dropdown-item');
      if (!item) return;
      hidden.value = item.dataset.value;
      input.value = item.textContent;
      list.classList.remove('open');
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#depsAddSuccDropdown')) list.classList.remove('open');
    });
  });
})();

// Добавляет последователя (POST /api/tasks/<succId>/dependencies/)
async function addSuccessor() {
  const succId = document.getElementById('depsAddSuccSelect').value;
  if (!succId) {
    notify('Выберите задачу', 'err');
    return;
  }
  const depType = document.getElementById('depsAddSuccType').value;
  const lagDays = parseInt(document.getElementById('depsAddSuccLag').value) || 0;
  try {
    // successor = выбранная задача, predecessor = текущая задача
    const res = await fetch(`/api/tasks/${parseInt(succId)}/dependencies/`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({
        predecessor_id: currentDepsTaskId,
        dep_type: depType,
        lag_days: lagDays,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      notify('Зависимость добавлена', 'ok');
      document.getElementById('depsAddSuccInput').value = '';
      document.getElementById('depsAddSuccSelect').value = '';
      loadDeps(currentDepsTaskId);
      // Обновить badges: у текущей задачи прибавился последователь (badge не меняется),
      // у выбранной задачи прибавился предшественник
      const succTask = tasks.find((t) => t.id === parseInt(succId));
      if (succTask) {
        succTask.predecessors_count = (succTask.predecessors_count || 0) + 1;
        const badge = document.querySelector(
          `[data-task-id="${succId}"] .dep-badge, tr[data-id="${succId}"] .dep-badge`,
        );
        if (badge) {
          badge.textContent = succTask.predecessors_count;
          badge.classList.remove('zero');
        }
      }
    } else {
      notify(data.error || 'Ошибка', 'err');
    }
  } catch (e) {
    console.error('addSuccessor error:', e);
    notify('Ошибка добавления', 'err');
  }
}

// Добавляет предшественника (POST /api/tasks/<currentId>/dependencies/)
async function addPredecessor() {
  const predId = document.getElementById('depsAddPredSelect').value;
  if (!predId) {
    notify('Выберите задачу', 'err');
    return;
  }
  const depType = document.getElementById('depsAddType').value;
  const lagDays = parseInt(document.getElementById('depsAddLag').value) || 0;
  try {
    const res = await fetch(`/api/tasks/${currentDepsTaskId}/dependencies/`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({
        predecessor_id: parseInt(predId),
        dep_type: depType,
        lag_days: lagDays,
      }),
    });
    const data = await res.json();
    if (res.ok) {
      notify('Зависимость добавлена', 'ok');
      document.getElementById('depsAddPredInput').value = '';
      document.getElementById('depsAddPredSelect').value = '';
      loadDeps(currentDepsTaskId);
      // Обновить badge в таблице
      _updateDepsBadge(currentDepsTaskId, 1);
    } else {
      notify(data.error || 'Ошибка', 'err');
    }
  } catch (e) {
    console.error('addPredecessor error:', e);
    notify('Ошибка добавления', 'err');
  }
}

// Удаляет зависимость (DELETE /api/dependencies/<depId>/) с подтверждением
async function deleteDep(depId) {
  if (!(await confirmDialog('Удалить эту зависимость?'))) return;
  try {
    const res = await fetch(`/api/dependencies/${depId}/`, {
      method: 'DELETE',
      headers: apiHeaders(),
    });
    if (res.ok) {
      notify('Зависимость удалена', 'ok');
      loadDeps(currentDepsTaskId);
      _updateDepsBadge(currentDepsTaskId, -1);
    } else {
      notify('Ошибка удаления', 'err');
    }
  } catch (e) {
    console.error('deleteDep error:', e);
    notify('Ошибка удаления', 'err');
  }
}

// Выравнивает даты задач по зависимостям (POST /api/tasks/<id>/align_dates/)
// cascade=true → выравнивает всех последователей, false → только текущую задачу
async function alignDates(cascade) {
  const msg = cascade
    ? 'Выровнять даты всех последователей по зависимостям?'
    : 'Выровнять даты этой задачи по предшественникам?';
  if (!(await confirmDialog(msg))) return;
  try {
    const res = await fetch(`/api/tasks/${currentDepsTaskId}/align_dates/`, {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ cascade: cascade }),
    });
    const data = await res.json();
    if (res.ok) {
      notify(`Даты выровнены (${data.aligned_count} задач)`, 'ok');
      loadDeps(currentDepsTaskId);
      loadTasks(); // Обновить всю таблицу
    } else {
      notify(data.error || 'Ошибка выравнивания', 'err');
    }
  } catch (e) {
    console.error('alignDates error:', e);
    notify('Ошибка выравнивания', 'err');
  }
}

function _updateDepsBadge(taskId, delta) {
  // Обновить счётчик в данных и в DOM
  const t = tasks.find((x) => x.id === taskId);
  if (t) t.predecessors_count = (t.predecessors_count || 0) + delta;
  const row = document.querySelector(`tr[data-id="${taskId}"]`);
  if (row) {
    const badge = row.querySelector('.dep-badge');
    if (badge && t) {
      const pc = t.predecessors_count || 0;
      badge.textContent = pc;
      badge.className = 'dep-badge' + (pc === 0 ? ' zero' : '');
      badge.title = pc > 0 ? `${pc} предш.` : 'Нет зависимостей';
    }
  }
}

// ── VIEW TABS — переключение между табличным видом и диаграммой Ганта ─────
let currentView = 'table'; // Текущий вид: 'table' или 'gantt'
let ganttLoaded = false; // Флаг: библиотека dhtmlxGantt загружена

let ganttDepsFilterActive = false; // Фильтр: показывать только задачи с зависимостями
let _ganttDepsSet = new Set(); // IDs задач, у которых есть зависимости

// Переключает вид (table ↔ gantt)
function switchView(view) {
  currentView = view;
  document.querySelectorAll('.view-tab').forEach((tab) => {
    tab.classList.toggle('active', tab.dataset.view === view);
  });
  const tableEl = document.getElementById('tableView');
  const ganttEl = document.getElementById('ganttContainer');
  const addRow = document.querySelector('.add-row-wrap');
  const filterBtn = document.getElementById('ganttFilterDeps');
  const scaleGroup = document.getElementById('ganttScaleGroup');

  tableEl.style.display = 'none';
  ganttEl.style.display = 'none';
  if (addRow) addRow.style.display = 'none';
  if (filterBtn) filterBtn.style.display = 'none';
  if (scaleGroup) scaleGroup.style.display = 'none';

  if (view === 'table') {
    tableEl.style.display = '';
    if (addRow) addRow.style.display = '';
    tableEl.classList.remove('spa-fade-in');
    void tableEl.offsetWidth;
    tableEl.classList.add('spa-fade-in');
  } else {
    ganttEl.style.display = 'block';
    ganttEl.classList.remove('spa-fade-in');
    void ganttEl.offsetWidth;
    ganttEl.classList.add('spa-fade-in');
    if (filterBtn) filterBtn.style.display = '';
    if (scaleGroup) scaleGroup.style.display = '';
    if (!ganttLoaded) {
      loadGantt();
      ganttLoaded = true;
    } else {
      renderGantt();
    }
  }
}

// Переключает фильтр «только задачи с зависимостями» на диаграмме Ганта
function toggleGanttDepsFilter() {
  ganttDepsFilterActive = !ganttDepsFilterActive;
  const btn = document.getElementById('ganttFilterDeps');
  btn.classList.toggle('active', ganttDepsFilterActive);
  renderGantt();
}

// Устанавливает масштаб диаграммы Ганта (day/week/month/year)
function setGanttScale(scale) {
  ganttSetScale(scale, 'gantt_scale', '#ganttScaleGroup');
}

function loadGantt() {
  ganttLoad(() => {
    setupGantt();
    renderGantt();
  }, 'ganttContainer');
}

const _SP_COL_KEY = 'sp_gantt_col_widths';
const _SP_COL_DEFAULTS = { text: 250, start_date: 90, end_date: 90, grid: 430 };

function setupGantt() {
  if (typeof gantt === 'undefined') return;
  ganttSetupBase();
  const savedCols = ganttLoadColWidths(_SP_COL_KEY, _SP_COL_DEFAULTS);
  gantt.config.grid_width = savedCols.grid;
  gantt.config.columns = [
    { name: 'text', label: 'Задача', width: savedCols.text, tree: false, resize: true },
    {
      name: 'start_date',
      label: 'Начало',
      align: 'center',
      width: savedCols.start_date,
      resize: true,
    },
    {
      name: 'end_date',
      label: 'Окончание',
      align: 'center',
      width: savedCols.end_date,
      resize: true,
    },
  ];
  gantt.config.readonly = !IS_WRITER;
  gantt.config.show_links = true;
  gantt.config.drag_links = false;
  gantt.config.drag_move = IS_WRITER;
  gantt.config.drag_resize = IS_WRITER;
  gantt.config.drag_progress = false;
  ganttRestoreScale('gantt_scale');
  gantt.init('ganttContainer');
  gantt.attachEvent('onGanttRender', () => ganttInjectResizers('ganttContainer', _SP_COL_KEY));

  // Drag → сохранение дат на сервере
  gantt.attachEvent('onAfterTaskDrag', function (id) {
    const task = gantt.getTask(id);
    if (!task) return;
    const startStr = ganttFormatDate(task.start_date);
    const endStr = ganttFormatDate(task.end_date);
    const srcTask = tasks.find((r) => r.id === id);
    const payload = { date_start: startStr, date_end: endStr };
    if (srcTask && srcTask.updated_at) payload.updated_at = srcTask.updated_at;
    fetchJson('/api/tasks/' + id + '/', {
      method: 'PUT',
      body: JSON.stringify(payload),
    })
      .then((res) => {
        if (res && res._conflict) {
          alert('Задачу изменил другой пользователь. Обновите страницу.');
          renderGantt();
          return;
        }
        const t = tasks.find((r) => r.id === id);
        if (t) {
          t.date_start = startStr;
          t.date_end = endStr;
          if (res && res.updated_at) t.updated_at = res.updated_at;
        }
        if (res._error) {
          alert('Ошибка сохранения дат');
          renderGantt();
        }
      })
      .catch(() => {
        alert('Ошибка сохранения');
        renderGantt();
      });
  });
}

// Загружает зависимости с сервера и отрисовывает диаграмму Ганта
async function renderGantt() {
  if (typeof gantt === 'undefined') return;
  try {
    // Загрузка связей
    const depsRes = await fetch('/api/dependencies/?context=plan', {
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    const deps = depsRes.ok ? await depsRes.json() : [];

    // Собрать ID задач, участвующих в зависимостях
    _ganttDepsSet = new Set();
    deps.forEach((d) => {
      _ganttDepsSet.add(d.source);
      _ganttDepsSet.add(d.target);
    });

    // Маппинг типов: FS=0, SS=1, FF=2, SF=3
    const typeMap = { FS: '0', SS: '1', FF: '2', SF: '3' };

    let filteredTasks = tasks.filter((t) => t.date_start && t.date_end);
    if (ganttDepsFilterActive) {
      filteredTasks = filteredTasks.filter((t) => _ganttDepsSet.has(t.id));
    }

    const ganttData = {
      data: filteredTasks.map((t) => ({
        id: t.id,
        text: t.work_name || t.work_num || '#' + t.id,
        start_date: t.date_start,
        end_date: t.date_end,
        department: t.dept || '',
      })),
      links: deps.map((d) => ({
        id: d.id,
        source: d.source,
        target: d.target,
        type: typeMap[d.type] || '0',
        lag: d.lag || 0,
      })),
    };

    gantt.clearAll();
    gantt.parse(ganttData);
    ganttAutoFitRowHeights();
    gantt.render();
  } catch (e) {
    console.error('renderGantt error:', e);
  }
}

// Sidebar toggle — управляется base.html, стили через .main-content.sidebar-collapsed в plan.css
// Экспорт — инициализация после загрузки export.js
buildExportDropdown('exportBtnContainer', {
  pageName: 'СП',
  columns: [
    { key: 'row_code', header: 'Код строки', width: 120 },
    { key: 'dept', header: 'Отдел', width: 80, forceText: true },
    { key: 'sector', header: 'Сектор', width: 100, forceText: true },
    { key: 'project', header: 'Проект', width: 140 },
    { key: 'work_name', header: 'Наименование', width: 240 },
    { key: 'work_number', header: 'Номер работы', width: 100 },
    { key: 'description', header: 'Описание', width: 200 },
    { key: 'executor', header: 'Исполнитель', width: 140 },
    { key: 'date_start', header: 'Начало (ПП)', width: 100 },
    { key: 'date_end', header: 'Окончание (ПП)', width: 100 },
    {
      key: 'plan_hours',
      header: 'Плановые часы',
      width: 100,
      format: (r) =>
        Object.values(r.plan_hours_all || {}).reduce((s, v) => s + (parseFloat(v) || 0), 0),
    },
    { key: 'stage', header: 'Этап', width: 120 },
    { key: 'justification', header: 'Обоснование', width: 200 },
  ],
  getAllData: () => tasks,
  getFilteredData: () => _spFiltered,
});

// Возвращает отфильтрованные задачи для экспорта (применяет colFilters + multi-select)
function spGetFilteredRows() {
  return tasks.filter((t) => {
    for (const [col, val] of Object.entries(colFilters)) {
      if (col.startsWith('mf_')) {
        const field = col.slice(3);
        if (val.size > 0) {
          if (field === 'executor') {
            const inS = val.has(t.executor || '');
            const inL = (t.executors_list || []).some((ex) => val.has(ex.name || ''));
            if (!inS && !inL) return false;
          } else if (field === 'has_deps') {
            const label = (t.predecessors_count || 0) > 0 ? 'Со связями' : 'Без связей';
            if (!val.has(label)) return false;
          } else {
            if (!val.has(t[field] || '')) return false;
          }
        }
        continue;
      }
      if (col === 'plan_hours_total') {
        const total = Object.values(t.plan_hours_all || {}).reduce(
          (s, v) => s + (parseFloat(v) || 0),
          0,
        );
        const thr = parseFloat(val);
        if (!isNaN(thr) && total < thr) return false;
        continue;
      }
      const cv = (t[col] || '').toString().toLowerCase();
      if (!cv.includes(val)) return false;
    }
    return true;
  });
}

/* PP-бейдж тултип — используется нативный title (кастомный удалён) */

/* ══════════════════════════════════════════════════════════════════════════
   Activity / Comments slideout panel  (UX audit #15)
   ══════════════════════════════════════════════════════════════════════════ */

let _activityWorkId = null;

function openActivityPanel(workId) {
  _activityWorkId = workId;
  const task = tasks.find((t) => t.id === workId);
  if (!task) return;

  // Title
  document.getElementById('activityTitle').textContent =
    task.work_name || task.description || 'Задача #' + workId;

  // Render details tab
  _renderActivityDetails(task);

  // Load comments
  _loadComments(workId);

  // Reset to details tab
  switchActivityTab('details');

  // Open panel
  document.getElementById('activityOverlay').classList.add('open');
  document.getElementById('activityPanel').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeActivityPanel() {
  document.getElementById('activityOverlay').classList.remove('open');
  document.getElementById('activityPanel').classList.remove('open');
  document.body.style.overflow = '';
  _activityWorkId = null;
}

function switchActivityTab(tab) {
  // Toggle tab buttons
  document.querySelectorAll('#activityPanel .slideout-tab').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  // Toggle tab content
  document.getElementById('activityDetails').style.display = tab === 'details' ? '' : 'none';
  document.getElementById('activityFeed').style.display = tab === 'activity' ? '' : 'none';
  // Show/hide comment input footer
  document.getElementById('activityFooter').style.display = tab === 'activity' ? '' : 'none';
}

function _renderActivityDetails(t) {
  const h = escapeHtml;
  const fmtDate = (d) => (d ? d.slice(0, 10).split('-').reverse().join('.') : '—');
  const status = _spGetStatus(t);
  const statusLabels = { done: 'Выполнено', overdue: 'Просрочено', inwork: 'В работе' };
  const statusClasses = { done: 'sp-done', overdue: 'sp-overdue', inwork: 'sp-inwork' };

  let html = '<div class="activity-detail-grid">';
  html += `<div class="activity-detail-row">
    <span class="activity-detail-label">Статус</span>
    <span class="ptc-status ${statusClasses[status]}" style="display:inline-block;padding:3px 10px;font-size:12px;pointer-events:none;">${statusLabels[status]}</span>
  </div>`;
  if (t.task_type) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Тип работы</span>
      <span class="activity-detail-value">${h(t.task_type)}</span>
    </div>`;
  }
  if (t.project) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Проект</span>
      <span class="activity-detail-value">${h(t.project)}</span>
    </div>`;
  }
  if (t.dept) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Отдел</span>
      <span class="activity-detail-value">${h(t.dept)}</span>
    </div>`;
  }
  if (t.sector) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Сектор</span>
      <span class="activity-detail-value">${h(t.sector)}</span>
    </div>`;
  }
  if (t.executor) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Исполнитель</span>
      <span class="activity-detail-value">${avatarHtml(t.executor, 'sm')} ${h(t.executor)}</span>
    </div>`;
  }
  html += `<div class="activity-detail-row">
    <span class="activity-detail-label">Начало</span>
    <span class="activity-detail-value">${fmtDate(t.date_start)}</span>
  </div>`;
  html += `<div class="activity-detail-row">
    <span class="activity-detail-label">Окончание</span>
    <span class="activity-detail-value">${fmtDate(t.date_end)}</span>
  </div>`;
  if (t.deadline) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Контрольный срок</span>
      <span class="activity-detail-value">${fmtDate(t.deadline)}</span>
    </div>`;
  }
  if (t.work_name) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Наименование</span>
      <span class="activity-detail-value">${h(t.work_name)}</span>
    </div>`;
  }
  if (t.description) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Описание</span>
      <span class="activity-detail-value">${h(t.description)}</span>
    </div>`;
  }
  if (t.justification) {
    html += `<div class="activity-detail-row">
      <span class="activity-detail-label">Основание</span>
      <span class="activity-detail-value">${h(t.justification)}</span>
    </div>`;
  }
  html += '</div>';
  document.getElementById('activityDetails').innerHTML = html;
}

async function _loadComments(workId) {
  const comments = await fetchJson('/api/comments/?work_id=' + workId);
  if (comments._error) {
    document.getElementById('activityFeed').innerHTML =
      '<div style="padding:20px;color:var(--muted);text-align:center;">Не удалось загрузить комментарии</div>';
    return;
  }
  renderActivityFeed(comments);
}

function renderActivityFeed(comments) {
  const container = document.getElementById('activityFeed');
  if (!comments || comments.length === 0) {
    container.innerHTML = '<div class="activity-empty">Комментариев пока нет. Будьте первым!</div>';
    return;
  }
  const h = escapeHtml;
  let html = '';
  comments.forEach((c) => {
    const dt = c.created_at ? new Date(c.created_at) : null;
    const timeStr = dt
      ? dt.toLocaleDateString('ru-RU') +
        ' ' +
        dt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
      : '';
    html += `<div class="comment-item" data-comment-id="${c.id}">
      <div class="comment-header">
        <span class="comment-author">${h(c.author || 'Аноним')}</span>
        <span class="comment-time">${timeStr}</span>
        <button class="comment-delete" onclick="deleteComment(${c.id})" title="Удалить"><i class="fas fa-trash-alt"></i></button>
      </div>
      <div class="comment-text">${h(c.text)}</div>
    </div>`;
  });
  container.innerHTML = html;
  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

async function postComment() {
  if (!_activityWorkId) return;
  const input = document.getElementById('commentInput');
  const text = (input.value || '').trim();
  if (!text) return;

  const comment = await fetchJson('/api/comments/', {
    method: 'POST',
    body: JSON.stringify({ work_id: _activityWorkId, text: text }),
  });
  if (comment._error) return; // toast уже показан в fetchJson
  input.value = '';
  // Reload comments
  _loadComments(_activityWorkId);
}

async function deleteComment(commentId) {
  if (!confirm('Удалить комментарий?')) return;
  const res = await fetchJson('/api/comments/' + commentId + '/', { method: 'DELETE' });
  if (res._error) return; // toast уже показан в fetchJson
  if (_activityWorkId) _loadComments(_activityWorkId);
}

// Ctrl+Enter to submit comment
document.addEventListener('keydown', function (e) {
  if (
    e.ctrlKey &&
    e.key === 'Enter' &&
    document.activeElement &&
    document.activeElement.id === 'commentInput'
  ) {
    postComment();
  }
  // Escape closes panel
  if (e.key === 'Escape' && _activityWorkId) {
    closeActivityPanel();
  }
});
