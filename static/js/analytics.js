/**
 * analytics.js — Единый модуль аналитики «Личный план».
 * Все фильтры — мульти-выбор (toggle чипов). Drill-down через таблицы.
 */
(function() {
'use strict';

/* ── Конфигурация из шаблона ──────────────────────────────────────────── */
var cfg = JSON.parse(document.getElementById('an-config').textContent);

/* Все фильтры — объекты {key: true} для мульти-выбора */
var currentYears    = {}; // {2026: true}
var currentMonths   = {}; // {3: true, 4: true}
var currentProjectIds = {};
var currentProductIds = {};
var currentDeptCodes  = {}; // {'021': true}
var currentSectorIds  = {};
var currentExecutorIds = {};

// Инициализируем текущий год
currentYears[cfg.currentYear] = true;

var MONTHS_RU = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];

var lastData = null;
var chartBar = null;

/* ── Утилиты ─────────────────────────────────────────────────────────── */
function esc(s) {
  if (!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function loadBadgeCls(pct) {
  if (pct <= 85) return 'ok';
  if (pct <= 100) return 'warn';
  return 'over';
}

function fmtPct(v) { return v > 0 ? v.toFixed(1) + '%' : '0%'; }
function fmtHrs(v) { return v > 0 ? v.toFixed(1) : '0'; }

function idsToList(obj) {
  var arr = [];
  for (var k in obj) { if (obj[k]) arr.push(k); }
  return arr;
}

function toggle(obj, key) {
  if (obj[key]) delete obj[key];
  else obj[key] = true;
}

function hasAny(obj) {
  for (var k in obj) { if (obj[k]) return true; }
  return false;
}

/* ── API ─────────────────────────────────────────────────────────────── */
function buildUrl() {
  var u = '/api/analytics/plan/';
  var params = [];

  var yrs = idsToList(currentYears);
  if (yrs.length) params.push('years=' + yrs.join(','));

  var mos = idsToList(currentMonths);
  if (mos.length) params.push('months=' + mos.join(','));

  var pids = idsToList(currentProjectIds);
  if (pids.length) params.push('project_ids=' + pids.join(','));

  var prids = idsToList(currentProductIds);
  if (prids.length) params.push('product_ids=' + prids.join(','));

  var dcs = idsToList(currentDeptCodes);
  if (dcs.length) params.push('dept_codes=' + dcs.map(encodeURIComponent).join(','));

  var sids = idsToList(currentSectorIds);
  if (sids.length) params.push('sector_ids=' + sids.join(','));

  var eids = idsToList(currentExecutorIds);
  if (eids.length) params.push('executor_ids=' + eids.join(','));

  return u + (params.length ? '?' + params.join('&') : '');
}

function loadData() {
  var el = document.getElementById('anContent');
  el.innerHTML = '<div class="an-loading"><i class="fas fa-spinner"></i> Загрузка...</div>';

  fetch(buildUrl())
  .then(function(r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(function(data) {
    if (data.error) {
      el.innerHTML = '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i>' + esc(data.error) + '</div>';
      return;
    }
    lastData = data;
    renderToolbar(data);
    renderBreadcrumb(data);
    renderContent(data);
  })
  .catch(function(e) {
    console.error('Analytics error:', e);
    el.innerHTML = '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i>Ошибка загрузки данных</div>';
  });
}

/* ── Навигация (мульти-toggle для всех фильтров) ─────────────────────── */
window.anToggleYear = function(y) { toggle(currentYears, y); if (!hasAny(currentYears)) currentYears[y] = true; loadData(); };
window.anClearYears = function() { currentYears = {}; currentYears[cfg.currentYear] = true; loadData(); };

window.anToggleMonth = function(m) { toggle(currentMonths, m); loadData(); };
window.anClearMonths = function() { currentMonths = {}; loadData(); };

window.anToggleProject = function(id) { toggle(currentProjectIds, id); _pruneProducts(); loadData(); };
window.anClearProjects = function() { currentProjectIds = {}; loadData(); };

window.anToggleProduct = function(id) { toggle(currentProductIds, id); loadData(); };
window.anClearProducts = function() { currentProductIds = {}; loadData(); };

window.anToggleDept = function(code) { toggle(currentDeptCodes, code); loadData(); };
window.anClearDepts = function() { currentDeptCodes = {}; loadData(); };

window.anToggleSector = function(id) { toggle(currentSectorIds, id); loadData(); };
window.anClearSectors = function() { currentSectorIds = {}; loadData(); };

window.anToggleExecutor = function(id) { toggle(currentExecutorIds, id); loadData(); };
window.anClearExecutors = function() { currentExecutorIds = {}; loadData(); };

// Drill-down через таблицы (ставит единственный фильтр)
window.anDrillDept = function(code) {
  currentDeptCodes = {}; currentDeptCodes[code] = true;
  currentSectorIds = {}; currentExecutorIds = {};
  loadData();
};
window.anDrillSector = function(id) {
  currentSectorIds = {}; currentSectorIds[id] = true;
  currentExecutorIds = {};
  loadData();
};
window.anDrillEmployee = function(id) {
  currentExecutorIds = {}; currentExecutorIds[id] = true;
  loadData();
};
window.anGoHome = function() {
  currentDeptCodes = {}; currentSectorIds = {}; currentExecutorIds = {};
  loadData();
};
window.anGoDept = function(code) {
  currentDeptCodes = {}; if (code) currentDeptCodes[code] = true;
  currentSectorIds = {}; currentExecutorIds = {};
  loadData();
};

function _pruneProducts() {
  var pids = idsToList(currentProjectIds);
  if (!pids.length) return;
  var allProducts = (lastData && lastData.nav_products) || [];
  var validIds = {};
  allProducts.forEach(function(p) {
    if (currentProjectIds[p.project_id]) validIds[p.id] = true;
  });
  for (var k in currentProductIds) {
    if (!validIds[k]) delete currentProductIds[k];
  }
}

/* ── Тулбар ──────────────────────────────────────────────────────────── */
function renderToolbar(data) {
  var tb = document.getElementById('anToolbar');
  var html = '';

  // Год (мульти-выбор, минимум 1)
  html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Год:</span><div class="an-chips">';
  (data.years || []).forEach(function(y) {
    var cls = currentYears[y] ? 'an-chip active' : 'an-chip';
    html += '<button class="' + cls + '" onclick="anToggleYear(' + y + ')">' + y + '</button>';
  });
  var yearCount = idsToList(currentYears).length;
  if (yearCount > 1) {
    html += '<button class="an-chip-clear" onclick="anClearYears()">сбросить</button>';
  }
  html += '</div></div>';

  // Месяц (мульти-выбор)
  html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Месяц:</span><div class="an-chips">';
  for (var m = 1; m <= 12; m++) {
    var cls = currentMonths[m] ? 'an-chip active' : 'an-chip';
    html += '<button class="' + cls + '" onclick="anToggleMonth(' + m + ')">' + MONTHS_RU[m-1] + '</button>';
  }
  if (hasAny(currentMonths)) {
    html += '<button class="an-chip-clear" onclick="anClearMonths()">сбросить</button>';
  }
  html += '</div></div>';

  // Проекты (мульти-выбор)
  var projects = data.nav_projects || [];
  if (projects.length > 0) {
    html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Проект:</span><div class="an-chips">';
    projects.forEach(function(p) {
      var cls = currentProjectIds[p.id] ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anToggleProject(' + p.id + ')">' + esc(p.name) + '</button>';
    });
    if (hasAny(currentProjectIds)) {
      html += '<button class="an-chip-clear" onclick="anClearProjects()">сбросить</button>';
    }
    html += '</div></div>';
  }

  // Изделия (фильтрованные по выбранным проектам)
  var allProducts = data.nav_products || [];
  var activeProjects = idsToList(currentProjectIds);
  var products = activeProjects.length > 0
    ? allProducts.filter(function(p) { return currentProjectIds[p.project_id]; })
    : allProducts;
  if (products.length > 0) {
    html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Изделие:</span><div class="an-chips">';
    products.forEach(function(p) {
      var cls = currentProductIds[p.id] ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anToggleProduct(' + p.id + ')">' + esc(p.name) + '</button>';
    });
    if (hasAny(currentProductIds)) {
      html += '<button class="an-chip-clear" onclick="anClearProducts()">сбросить</button>';
    }
    html += '</div></div>';
  }

  // Отделы (мульти-выбор чипами)
  var depts = data.nav_depts || [];
  if (depts.length > 0) {
    html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Отдел:</span><div class="an-chips">';
    depts.forEach(function(code) {
      var cls = currentDeptCodes[code] ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anToggleDept(\'' + esc(code) + '\')">' + esc(code) + '</button>';
    });
    if (hasAny(currentDeptCodes)) {
      html += '<button class="an-chip-clear" onclick="anClearDepts()">сбросить</button>';
    }
    html += '</div></div>';
  }

  // Секторы (мульти-выбор чипами)
  var sectors = data.nav_sectors || [];
  if (sectors.length > 0) {
    html += '<div class="an-toolbar-panel"><span class="an-toolbar-label">Сектор:</span><div class="an-chips">';
    sectors.forEach(function(s) {
      var cls = currentSectorIds[s.id] ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anToggleSector(' + s.id + ')">' + esc(s.name) + '</button>';
    });
    if (hasAny(currentSectorIds)) {
      html += '<button class="an-chip-clear" onclick="anClearSectors()">сбросить</button>';
    }
    html += '</div></div>';
  }

  tb.innerHTML = html;
}

/* ── Хлебные крошки ──────────────────────────────────────────────────── */
function renderBreadcrumb(data) {
  var bc = document.getElementById('anBreadcrumb');
  var parts = [];

  var role = data.role_info ? data.role_info.role : 'user';
  var canGoHome = role === 'admin' || role === 'ntc_head' || role === 'ntc_deputy';

  if (data.view === 'all') {
    parts.push('<span style="font-weight:600;">Все отделы</span>');
  } else if (data.view === 'dept') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()">Все отделы</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;">' + esc(data.dept ? data.dept.name || data.dept.code : '') + '</span>');
  } else if (data.view === 'sector') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()">Все отделы</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    var deptCodes = idsToList(currentDeptCodes);
    if (deptCodes.length || (data.role_info && (role === 'dept_head' || role === 'dept_deputy'))) {
      var deptCode = deptCodes[0] || data.role_info.dept;
      parts.push('<a class="an-breadcrumb-link" onclick="anGoDept(\'' + esc(deptCode) + '\')">' + esc(deptCode) + '</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;">Сектор: ' + esc(data.sector ? data.sector.name : '') + '</span>');
  } else if (data.view === 'employee') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()">Все отделы</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    var empInfo = data.employee || {};
    if (empInfo.dept) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoDept(\'' + esc(empInfo.dept) + '\')">' + esc(empInfo.dept) + '</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;">' + esc(empInfo.name) + '</span>');
  } else if (data.view === 'employees') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()">Все отделы</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;">Выбранные сотрудники</span>');
  }

  bc.innerHTML = parts.join(' ');
}

/* ── Контент по типу view ────────────────────────────────────────────── */
function renderContent(data) {
  var el = document.getElementById('anContent');

  switch (data.view) {
    case 'all':       renderAllDepts(el, data); break;
    case 'dept':      renderDept(el, data); break;
    case 'sector':    renderSector(el, data); break;
    case 'employee':  renderEmployee(el, data); break;
    case 'employees': renderSector(el, data); break;  // та же разметка — список сотрудников
    default:
      el.innerHTML = '<div class="an-empty"><i class="fas fa-chart-bar"></i>Нет данных</div>';
  }
}

/* ── View: все отделы ────────────────────────────────────────────────── */
function renderAllDepts(el, data) {
  var depts = data.depts || [];
  if (!depts.length) {
    el.innerHTML = '<div class="an-empty"><i class="fas fa-building"></i>Нет данных по отделам</div>';
    return;
  }

  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  html += '<div class="an-widget an-widget-full" style="padding:0;">';
  html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-building"></i> Отделы</div>';
  html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
  html += '<table class="an-list-table"><thead><tr>';
  html += '<th>Отдел</th><th>Название</th><th class="cell-num">Сотрудников</th>';
  html += '<th class="cell-num">План (ч)</th><th class="cell-num">Норма (ч)</th><th class="cell-num">Загрузка</th>';
  html += '</tr></thead><tbody>';

  depts.forEach(function(d) {
    var badgeCls = loadBadgeCls(d.total_load_pct);
    html += '<tr onclick="anDrillDept(\'' + esc(d.code) + '\')">';
    html += '<td><strong>' + esc(d.code) + '</strong></td>';
    html += '<td>' + esc(d.name) + '</td>';
    html += '<td class="cell-num">' + (d.employee_count || 0) + '</td>';
    html += '<td class="cell-num">' + fmtHrs(d.total_planned) + '</td>';
    html += '<td class="cell-num">' + fmtHrs(d.total_norm) + '</td>';
    html += '<td class="cell-num"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(d.total_load_pct) + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ── View: отдел ─────────────────────────────────────────────────────── */
function renderDept(el, data) {
  var sectors = data.sectors || [];
  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  if (sectors.length > 0) {
    html += '<div class="an-widget an-widget-full" style="padding:0;">';
    html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-layer-group"></i> Секторы</div>';
    html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
    html += '<table class="an-list-table"><thead><tr>';
    html += '<th>Сектор</th><th class="cell-num">Сотрудников</th>';
    html += '<th class="cell-num">План (ч)</th><th class="cell-num">Норма (ч)</th><th class="cell-num">Загрузка</th>';
    html += '</tr></thead><tbody>';

    sectors.forEach(function(s) {
      var badgeCls = loadBadgeCls(s.total_load_pct);
      var empCount = (s.employees || []).length;
      html += '<tr onclick="anDrillSector(' + s.id + ')">';
      html += '<td><strong>' + esc(s.name) + '</strong></td>';
      html += '<td class="cell-num">' + empCount + '</td>';
      html += '<td class="cell-num">' + fmtHrs(s.total_planned) + '</td>';
      html += '<td class="cell-num">' + fmtHrs(s.total_norm) + '</td>';
      html += '<td class="cell-num"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(s.total_load_pct) + '</span></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div></div>';
  }

  sectors.forEach(function(s) {
    if (s.employees && s.employees.length > 0) {
      html += renderEmployeesList(s.employees, 'Сотрудники — ' + esc(s.name));
    }
  });

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ── View: сектор ────────────────────────────────────────────────────── */
function renderSector(el, data) {
  var employees = data.employees || [];
  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  html += renderEmployeesList(employees, data.view === 'employees' ? 'Выбранные сотрудники' : 'Сотрудники сектора');

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ── View: сотрудник ─────────────────────────────────────────────────── */
function renderEmployee(el, data) {
  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-calendar-alt"></i> Помесячная разбивка</div>';
  html += renderMonthsTable(data.months || []);
  html += '</div></div>';

  var tasks = data.tasks || [];
  html += '<div class="an-widget an-widget-full" style="padding:0;">';
  html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-tasks"></i> Задачи (' + tasks.length + ')';
  html += '<span class="an-legend"><span class="an-active-mark"></span> период выполнения';
  html += ' &nbsp; <span class="an-abs-mark an-abs-vac"></span> отпуск';
  html += ' &nbsp; <span class="an-abs-mark an-abs-trip"></span> командировка</span>';
  html += '</div>';

  if (tasks.length === 0) {
    html += '<div class="an-empty"><i class="fas fa-clipboard-check"></i>Нет задач</div>';
  } else {
    html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
    html += '<table class="an-tasks-table"><thead><tr>';
    html += '<th>Название</th><th>Проект</th><th>Начало</th><th>Окончание</th>';
    for (var m = 1; m <= 12; m++) {
      html += '<th class="cell-num" style="font-size:10px;" title="Плановые часы / период выполнения задачи">' + MONTHS_RU[m-1] + '</th>';
    }
    html += '<th class="cell-num">Итого (ч)</th><th>Статус</th>';
    html += '</tr></thead><tbody>';

    var selYears = idsToList(currentYears);

    // Строка отпусков/командировок
    var absences = data.absences || [];
    if (absences.length > 0) {
      var absMonths = {};  // {month: [{type, label}]}
      absences.forEach(function(a) {
        selYears.forEach(function(y) {
          var yInt = parseInt(y);
          var ds = new Date(a.date_start);
          var de = new Date(a.date_end);
          for (var mm = 1; mm <= 12; mm++) {
            var mStart = new Date(yInt, mm - 1, 1);
            var mEnd = new Date(yInt, mm, 0);
            if (mEnd >= ds && mStart <= de) {
              if (!absMonths[mm]) absMonths[mm] = [];
              absMonths[mm].push({type: a.type, label: a.label});
            }
          }
        });
      });
      html += '<tr class="an-absence-row">';
      html += '<td colspan="4" style="font-weight:600;color:var(--muted);font-size:12px;"><i class="fas fa-plane-departure" style="margin-right:4px;"></i>Отпуска / командировки</td>';
      for (var m = 1; m <= 12; m++) {
        var items = absMonths[m] || [];
        if (items.length > 0) {
          var marks = '';
          var titles = [];
          items.forEach(function(it) {
            var cls = it.type === 'vacation' ? 'an-abs-vac' : 'an-abs-trip';
            marks += '<span class="an-abs-mark ' + cls + '"></span>';
            if (titles.indexOf(it.label) === -1) titles.push(it.label);
          });
          html += '<td class="cell-num" title="' + esc(titles.join('; ')) + '">' + marks + '</td>';
        } else {
          html += '<td class="cell-num"></td>';
        }
      }
      html += '<td class="cell-num"></td><td></td></tr>';
    }

    tasks.forEach(function(t) {
      var dsF = t.date_start ? t.date_start.slice(8,10) + '.' + t.date_start.slice(5,7) + '.' + t.date_start.slice(0,4) : '—';
      var deF = t.date_end ? t.date_end.slice(8,10) + '.' + t.date_end.slice(5,7) + '.' + t.date_end.slice(0,4) : '—';
      var statusCls = 'an-badge-status an-badge-' + t.status;
      var statusText = t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просроч.' : 'В работе');

      // Активные месяцы по date_start/date_end
      var activeMonths = {};
      if (t.date_start || t.date_end) {
        selYears.forEach(function(y) {
          var yInt = parseInt(y);
          var ds = t.date_start ? new Date(t.date_start) : null;
          var de = t.date_end ? new Date(t.date_end) : null;
          for (var mm = 1; mm <= 12; mm++) {
            var mStart = new Date(yInt, mm - 1, 1);
            var mEnd = new Date(yInt, mm, 0);
            if ((!ds || mEnd >= ds) && (!de || mStart <= de)) activeMonths[mm] = true;
          }
        });
      }

      html += '<tr>';
      html += '<td>' + esc(t.work_name) + '</td>';
      html += '<td>' + esc(t.project || t.project_name) + '</td>';
      html += '<td style="white-space:nowrap">' + dsF + '</td>';
      html += '<td style="white-space:nowrap">' + deF + '</td>';

      var rowTotal = 0;
      // Проверяем есть ли вообще plan_hours у задачи
      var hasPlanHours = false;
      if (t.plan_hours) {
        for (var k in t.plan_hours) {
          if (t.plan_hours[k]) { hasPlanHours = true; break; }
        }
      }

      for (var m = 1; m <= 12; m++) {
        var hrs = 0;
        selYears.forEach(function(y) {
          var key = y + '-' + (m < 10 ? '0' + m : m);
          if (t.plan_hours && t.plan_hours[key]) hrs += parseFloat(t.plan_hours[key]);
        });
        rowTotal += hrs;
        if (hrs > 0) {
          html += '<td class="cell-num">' + hrs.toFixed(1) + '</td>';
        } else if (!hasPlanHours && activeMonths[m]) {
          html += '<td class="cell-num"><span class="an-active-mark" title="Период выполнения"></span></td>';
        } else {
          html += '<td class="cell-num"></td>';
        }
      }
      html += '<td class="cell-num"><strong>' + (rowTotal > 0 ? rowTotal.toFixed(1) : '') + '</strong></td>';
      html += '<td><span class="' + statusCls + '">' + statusText + '</span></td>';
      html += '</tr>';
    });
    html += '</tbody></table></div>';
  }
  html += '</div>';

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ── Компоненты ──────────────────────────────────────────────────────── */
function renderSummaryCards(data) {
  var planned = data.total_planned || 0;
  var norm = data.total_norm || 0;
  var load = data.total_load_pct || 0;
  var loadCls = loadBadgeCls(load);
  var colorMap = {ok: 'an-val-green', warn: 'an-val-yellow', over: 'an-val-red'};

  var html = '<div class="an-summary">';
  html += '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' + fmtHrs(planned) + '</div><div class="an-summary-label">План (ч)</div></div>';
  html += '<div class="an-summary-card"><div class="an-summary-val">' + fmtHrs(norm) + '</div><div class="an-summary-label">Норма (ч)</div></div>';
  html += '<div class="an-summary-card"><div class="an-summary-val ' + (colorMap[loadCls] || '') + '">' + fmtPct(load) + '</div><div class="an-summary-label">Загрузка</div></div>';

  if (data.tasks) {
    html += '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' + data.tasks.length + '</div><div class="an-summary-label">Задач</div></div>';
  }

  html += '</div>';
  return html;
}

function renderEmployeesList(employees, title) {
  if (!employees || !employees.length) return '';

  var html = '<div class="an-widget an-widget-full" style="padding:0;">';
  html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-users"></i> ' + (title || 'Сотрудники') + '</div>';
  html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
  html += '<table class="an-list-table"><thead><tr>';
  html += '<th>Сотрудник</th>';
  for (var m = 1; m <= 12; m++) {
    html += '<th class="cell-num" style="font-size:10px;">' + MONTHS_RU[m-1] + '</th>';
  }
  html += '<th class="cell-num">Итого</th><th class="cell-num">Загрузка</th>';
  html += '</tr></thead><tbody>';

  employees.forEach(function(e) {
    var badgeCls = loadBadgeCls(e.total_load_pct);
    html += '<tr onclick="anDrillEmployee(' + e.id + ')">';
    html += '<td><strong>' + esc(e.name) + '</strong></td>';

    var months = e.months || [];
    for (var m = 0; m < 12; m++) {
      var planned = months[m] ? months[m].planned : 0;
      html += '<td class="cell-num">' + (planned > 0 ? planned.toFixed(1) : '') + '</td>';
    }

    html += '<td class="cell-num"><strong>' + fmtHrs(e.total_planned) + '</strong></td>';
    html += '<td class="cell-num"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(e.total_load_pct) + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  return html;
}

function renderMonthsTable(months) {
  var html = '<table class="an-months-table"><thead><tr><th></th><th>План</th><th>Норма</th><th>Загрузка</th></tr></thead><tbody>';

  months.forEach(function(m, i) {
    var badgeCls = loadBadgeCls(m.load_pct);
    html += '<tr>';
    html += '<td class="row-label">' + MONTHS_RU[i] + '</td>';
    html += '<td>' + fmtHrs(m.planned) + '</td>';
    html += '<td>' + fmtHrs(m.norm) + '</td>';
    html += '<td><span class="an-load-badge ' + badgeCls + '">' + fmtPct(m.load_pct) + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  return html;
}

/* ── График ──────────────────────────────────────────────────────────── */
function renderBarChart(months) {
  var canvas = document.getElementById('anChart');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (chartBar) chartBar.destroy();

  var accent = getCSSVar('--accent') || '#3b82f6';
  var muted = getCSSVar('--muted') || '#888';

  var planned = months.map(function(m) { return m.planned; });
  var norms = months.map(function(m) { return m.norm; });

  chartBar = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: MONTHS_RU,
      datasets: [
        {
          label: 'План (ч)',
          data: planned,
          backgroundColor: accent + '88',
          borderColor: accent,
          borderWidth: 1
        },
        {
          label: 'Норма (ч)',
          data: norms,
          type: 'line',
          borderColor: '#ef4444',
          borderWidth: 2,
          borderDash: [6, 3],
          pointRadius: 3,
          pointBackgroundColor: '#ef4444',
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 12 }, color: getCSSVar('--text') || '#333' } }
      },
      scales: {
        x: { ticks: { color: muted }, grid: { display: false } },
        y: { beginAtZero: true, ticks: { color: muted }, grid: { color: getCSSVar('--border') || '#eee' } }
      }
    }
  });
}

/* ── Init ─────────────────────────────────────────────────────────────── */
loadData();

})();
