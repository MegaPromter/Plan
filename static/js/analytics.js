/**
 * analytics.js — Единый модуль аналитики «Личный план».
 * Режимы: Графики / Таблицы (переключатель).
 * Все фильтры — мульти-выбор (toggle чипов). Drill-down через таблицы.
 */
(function() {
'use strict';

/* ── Конфигурация из шаблона ──────────────────────────────────────────── */
var cfg = JSON.parse(document.getElementById('an-config').textContent);

/* ── Режим отображения ────────────────────────────────────────────────── */
var currentMode = 'charts';  // 'charts' | 'tables'

/* Все фильтры — объекты {key: true} для мульти-выбора */
var currentYears    = {};
var currentMonths   = {};
var currentProjectIds = {};
var currentProductIds = {};
var currentDeptCodes  = {};
var currentSectorIds  = {};
var currentExecutorIds = {};

currentYears[cfg.currentYear] = true;

var MONTHS_RU = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];

var lastData = null;
var chartBar = null;
var _exportData = [];

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

/* ── Переключение режимов ─────────────────────────────────────────────── */
window.anSetMode = function(mode) {
  currentMode = mode;
  updateModeTabs();
  if (lastData) {
    renderContent(lastData);
  }
};

function updateModeTabs() {
  var tabs = document.querySelectorAll('#anModeTabs .an-mode-tab');
  tabs.forEach(function(tab) {
    if (tab.getAttribute('data-mode') === currentMode) {
      tab.classList.add('active');
    } else {
      tab.classList.remove('active');
    }
  });
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
      el.innerHTML = '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> ' + esc(data.error) + '</div>';
      return;
    }
    lastData = data;
    try {
      renderToolbar(data);
      renderBreadcrumb(data);
      renderContent(data);
    } catch (renderErr) {
      console.error('Analytics render error:', renderErr);
      el.innerHTML = '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> Ошибка отображения данных</div>';
    }
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
window.anClearProjects = function() { currentProjectIds = {}; currentProductIds = {}; loadData(); };

window.anToggleProduct = function(id) { toggle(currentProductIds, id); loadData(); };
window.anClearProducts = function() { currentProductIds = {}; loadData(); };

window.anToggleDept = function(code) { toggle(currentDeptCodes, code); currentSectorIds = {}; currentExecutorIds = {}; loadData(); };
window.anClearDepts = function() { currentDeptCodes = {}; currentSectorIds = {}; currentExecutorIds = {}; loadData(); };

window.anToggleSector = function(id) { toggle(currentSectorIds, id); currentExecutorIds = {}; loadData(); };
window.anClearSectors = function() { currentSectorIds = {}; currentExecutorIds = {}; loadData(); };

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
    parts.push('<span style="font-weight:600;"><i class="fas fa-building" style="margin-right:4px;color:var(--accent);"></i>НТЦ — Все отделы</span>');
  } else if (data.view === 'dept') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-building"></i> НТЦ</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;"><i class="fas fa-layer-group" style="margin-right:4px;color:var(--accent);"></i>Отдел ' + esc(data.dept ? data.dept.name || data.dept.code : '') + '</span>');
  } else if (data.view === 'sector') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-building"></i> НТЦ</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    var deptCodes = idsToList(currentDeptCodes);
    if (deptCodes.length || (data.role_info && (role === 'dept_head' || role === 'dept_deputy'))) {
      var deptCode = deptCodes[0] || data.role_info.dept;
      parts.push('<a class="an-breadcrumb-link" onclick="anGoDept(\'' + esc(deptCode) + '\')">' + esc(deptCode) + '</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;"><i class="fas fa-users" style="margin-right:4px;color:var(--accent);"></i>Сектор ' + esc(data.sector ? data.sector.name : '') + '</span>');
  } else if (data.view === 'employee') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-building"></i> НТЦ</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    var empInfo = data.employee || {};
    if (empInfo.dept) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoDept(\'' + esc(empInfo.dept) + '\')">' + esc(empInfo.dept) + '</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;"><i class="fas fa-user" style="margin-right:4px;color:var(--accent);"></i>' + esc(empInfo.name) + '</span>');
  } else if (data.view === 'employees') {
    if (canGoHome) {
      parts.push('<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-building"></i> НТЦ</a>');
      parts.push('<span class="an-breadcrumb-sep">›</span>');
    }
    parts.push('<span style="font-weight:600;">Выбранные сотрудники</span>');
  }

  bc.innerHTML = parts.join(' ');
}

/* ── Контент — маршрутизация по режиму и view ─────────────────────────── */
function renderContent(data) {
  var el = document.getElementById('anContent');

  // Очищаем экспорт — будет пересоздан в табличном режиме
  var expTop = document.getElementById('anExportTop');
  if (expTop) expTop.innerHTML = '';

  if (currentMode === 'charts') {
    switch (data.view) {
      case 'all':       renderAllDeptsCharts(el, data); break;
      case 'dept':      renderDeptCharts(el, data); break;
      case 'sector':    renderSectorCharts(el, data); break;
      case 'employee':  renderEmployeeCharts(el, data); break;
      case 'employees': renderSectorCharts(el, data); break;
      default:
        el.innerHTML = '<div class="an-empty"><i class="fas fa-chart-bar"></i>Нет данных</div>';
    }
  } else {
    switch (data.view) {
      case 'all':       renderAllDeptsTables(el, data); break;
      case 'dept':      renderDeptTables(el, data); break;
      case 'sector':    renderSectorTables(el, data); break;
      case 'employee':  renderEmployeeTables(el, data); break;
      case 'employees': renderSectorTables(el, data); break;
      default:
        el.innerHTML = '<div class="an-empty"><i class="fas fa-table"></i>Нет данных</div>';
    }
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   РЕЖИМ «ГРАФИКИ» — графики + таблицы drill-down
   ═══════════════════════════════════════════════════════════════════════ */

function renderAllDeptsCharts(el, data) {
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

function renderDeptCharts(el, data) {
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

function renderSectorCharts(el, data) {
  var employees = data.employees || [];
  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  html += renderEmployeesList(employees, data.view === 'employees' ? 'Выбранные сотрудники' : 'Сотрудники сектора');

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

function renderEmployeeCharts(el, data) {
  var html = renderSummaryCards(data);

  html += '<div class="an-widgets">';
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-calendar-alt"></i> Помесячная разбивка</div>';
  html += renderMonthsTable(data.months || []);
  html += '</div></div>';

  html += renderTasksBlock(data);

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ═══════════════════════════════════════════════════════════════════════
   РЕЖИМ «ТАБЛИЦЫ» — карточки + таблицы + экспорт (из reports.js)
   ═══════════════════════════════════════════════════════════════════════ */

function renderAllDeptsTables(el, data) {
  var depts = data.depts || [];
  if (!depts.length) {
    el.innerHTML = '<div class="an-empty"><i class="fas fa-building"></i>Нет данных по отделам</div>';
    return;
  }

  _exportData = depts.map(function(d) {
    return {
      dept_code: d.code, dept_name: d.name || '',
      employees: d.employee_count || 0,
      planned: d.total_planned || 0, norm: d.total_norm || 0,
      load_pct: d.total_load_pct || 0
    };
  });

  var html = renderSummaryCards(data);

  html += '<div class="rpt-level-header">';
  html += '<div class="rpt-level-title"><i class="fas fa-building"></i> Отделы (' + depts.length + ')</div>';
  html += '<div class="rpt-export-bar" id="anExportInline"></div>';
  html += '</div>';

  html += '<div class="rpt-cards">';
  depts.forEach(function(d) {
    var badgeCls = loadBadgeCls(d.total_load_pct);
    var barW = Math.min(d.total_load_pct || 0, 150);
    html += '<div class="rpt-card" onclick="anDrillDept(\'' + esc(d.code) + '\')">';
    html += '<div class="rpt-card-header">';
    html += '<div class="rpt-card-title"><i class="fas fa-layer-group"></i>' + esc(d.code) + '</div>';
    html += '<span class="rpt-card-arrow"><i class="fas fa-chevron-right"></i></span>';
    html += '</div>';
    if (d.name) html += '<div class="rpt-card-subtitle">' + esc(d.name) + '</div>';
    html += '<div class="rpt-card-metrics">';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val an-val-accent">' + fmtHrs(d.total_planned) + '</div><div class="rpt-card-metric-label">план (ч)</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val">' + fmtHrs(d.total_norm) + '</div><div class="rpt-card-metric-label">норма</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(d.total_load_pct) + '</span></div><div class="rpt-card-metric-label">загрузка</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val">' + (d.employee_count || 0) + '</div><div class="rpt-card-metric-label">сотр.</div></div>';
    html += '</div>';
    html += '<div class="rpt-card-bar"><div class="rpt-card-bar-fill ' + badgeCls + '" style="width:' + barW + '%"></div></div>';
    html += '</div>';
  });
  html += '</div>';

  el.innerHTML = html;
  _buildExport('anExportContainer', 'Отчёт_НТЦ', _deptExportCols());
}

function renderDeptTables(el, data) {
  var sectors = data.sectors || [];

  _exportData = [];
  sectors.forEach(function(s) {
    (s.employees || []).forEach(function(e) {
      _exportData.push(_empExportRow(e, data.dept ? data.dept.code : '', s.name));
    });
  });

  var deptName = data.dept ? (data.dept.name || data.dept.code) : '';
  var html = renderSummaryCards(data);

  html += '<div class="rpt-level-header">';
  html += '<div class="rpt-level-title"><i class="fas fa-layer-group"></i> ' + esc(deptName) + ' — Секторы (' + sectors.length + ')</div>';
  html += '<div class="rpt-export-bar" id="anExportInline"></div>';
  html += '</div>';

  if (sectors.length === 0) {
    html += '<div class="an-empty"><i class="fas fa-layer-group"></i>Нет секторов</div>';
    el.innerHTML = html;
    return;
  }

  html += '<div class="rpt-cards">';
  sectors.forEach(function(s) {
    var badgeCls = loadBadgeCls(s.total_load_pct);
    var empCount = (s.employees || []).length;
    var barW = Math.min(s.total_load_pct || 0, 150);
    html += '<div class="rpt-card" onclick="anDrillSector(' + s.id + ')">';
    html += '<div class="rpt-card-header">';
    html += '<div class="rpt-card-title"><i class="fas fa-users"></i>' + esc(s.name) + '</div>';
    html += '<span class="rpt-card-arrow"><i class="fas fa-chevron-right"></i></span>';
    html += '</div>';
    html += '<div class="rpt-card-metrics">';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val an-val-accent">' + fmtHrs(s.total_planned) + '</div><div class="rpt-card-metric-label">план</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val">' + fmtHrs(s.total_norm) + '</div><div class="rpt-card-metric-label">норма</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(s.total_load_pct) + '</span></div><div class="rpt-card-metric-label">загрузка</div></div>';
    html += '<div class="rpt-card-metric"><div class="rpt-card-metric-val">' + empCount + '</div><div class="rpt-card-metric-label">сотр.</div></div>';
    html += '</div>';
    html += '<div class="rpt-card-bar"><div class="rpt-card-bar-fill ' + badgeCls + '" style="width:' + barW + '%"></div></div>';
    html += '</div>';
  });
  html += '</div>';

  sectors.forEach(function(s) {
    if (s.employees && s.employees.length > 0) {
      html += _renderEmpTable(s.employees, 'Сотрудники — ' + esc(s.name));
    }
  });

  el.innerHTML = html;
  _buildExport('anExportContainer', 'Отчёт_' + (data.dept ? data.dept.code : ''), _empExportCols());
}

function renderSectorTables(el, data) {
  var employees = data.employees || [];
  var title = data.view === 'employees' ? 'Выбранные сотрудники' : 'Сотрудники сектора';

  _exportData = employees.map(function(e) {
    var deptCodes = idsToList(currentDeptCodes);
    return _empExportRow(e, deptCodes[0] || '', data.sector ? data.sector.name : '');
  });

  var html = renderSummaryCards(data);

  html += '<div class="rpt-level-header">';
  html += '<div class="rpt-level-title"><i class="fas fa-users"></i> ' + esc(title) + ' (' + employees.length + ')</div>';
  html += '<div class="rpt-export-bar" id="anExportInline"></div>';
  html += '</div>';

  html += _renderEmpTable(employees, null);

  el.innerHTML = html;
  _buildExport('anExportContainer', 'Отчёт_сектор', _empExportCols());
}

function renderEmployeeTables(el, data) {
  var emp = data.employee || {};
  var tasks = data.tasks || [];
  var selYears = idsToList(currentYears);

  _exportData = tasks.map(function(t) {
    var row = {
      work_name: t.work_name, project: t.project_name || t.project || '',
      date_start: t.date_start || '', date_end: t.date_end || '',
      status: t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просрочено' : 'В работе')
    };
    var total = 0;
    for (var m = 1; m <= 12; m++) {
      var hrs = 0;
      selYears.forEach(function(y) {
        var key = y + '-' + (m < 10 ? '0' + m : m);
        if (t.plan_hours && t.plan_hours[key]) hrs += parseFloat(t.plan_hours[key]);
      });
      row['m' + m] = hrs;
      total += hrs;
    }
    row.total_hours = total;
    return row;
  });

  // Собираем отпуска/командировки по месяцам
  var absences = data.absences || [];
  var absMonths = {};
  absences.forEach(function(a) {
    var dsLabel = a.date_start ? a.date_start.slice(8,10) + '.' + a.date_start.slice(5,7) : '';
    var deLabel = a.date_end ? a.date_end.slice(8,10) + '.' + a.date_end.slice(5,7) : '';
    var fullLabel = a.label + ': ' + dsLabel + ' – ' + deLabel;
    selYears.forEach(function(y) {
      var yInt = parseInt(y);
      var ds = new Date(a.date_start);
      var de = new Date(a.date_end);
      for (var mm = 1; mm <= 12; mm++) {
        var mStart = new Date(yInt, mm - 1, 1);
        var mEnd = new Date(yInt, mm, 0);
        if (mEnd >= ds && mStart <= de) {
          if (!absMonths[mm]) absMonths[mm] = {vac: false, trip: false, titles: []};
          if (a.type === 'vacation') absMonths[mm].vac = true;
          else absMonths[mm].trip = true;
          if (absMonths[mm].titles.indexOf(fullLabel) === -1) absMonths[mm].titles.push(fullLabel);
        }
      }
    });
  });

  var html = renderSummaryCards(data);

  // Помесячная таблица (план/норма/загрузка + отпуска)
  var months = data.months || [];
  if (months.length > 0) {
    html += '<div class="rpt-tasks-wrap" style="margin-bottom:16px;">';
    html += '<div class="rpt-tasks-header"><div class="rpt-tasks-title"><i class="fas fa-calendar-alt"></i> Помесячная загрузка</div></div>';
    html += '<div style="overflow-x:auto;padding:0 14px 14px;">';
    html += '<table class="an-months-table"><thead><tr><th></th>';
    for (var m = 1; m <= 12; m++) html += '<th>' + MONTHS_RU[m-1] + '</th>';
    html += '<th>Итого</th></tr></thead><tbody>';

    html += '<tr><td class="row-label">План</td>';
    var sumP = 0;
    for (var m = 1; m <= 12; m++) {
      var md = months.find(function(x) { return x.month === m; });
      var p = md ? md.planned : 0; sumP += p;
      html += '<td>' + (p > 0 ? fmtHrs(p) : '') + '</td>';
    }
    html += '<td><strong>' + fmtHrs(sumP) + '</strong></td></tr>';

    html += '<tr><td class="row-label">Норма</td>';
    var sumN = 0;
    for (var m = 1; m <= 12; m++) {
      var md = months.find(function(x) { return x.month === m; });
      var n = md ? md.norm : 0; sumN += n;
      html += '<td>' + (n > 0 ? fmtHrs(n) : '') + '</td>';
    }
    html += '<td><strong>' + fmtHrs(sumN) + '</strong></td></tr>';

    html += '<tr><td class="row-label">Загрузка</td>';
    for (var m = 1; m <= 12; m++) {
      var md = months.find(function(x) { return x.month === m; });
      var lp = md ? md.load_pct : 0;
      var bc = loadBadgeCls(lp);
      html += '<td><span class="an-load-badge ' + bc + '">' + fmtPct(lp) + '</span></td>';
    }
    var totalLoad = sumN > 0 ? sumP / sumN * 100 : 0;
    var totalBC = loadBadgeCls(totalLoad);
    html += '<td><span class="an-load-badge ' + totalBC + '">' + fmtPct(totalLoad) + '</span></td></tr>';

    // Строка отпусков/командировок
    if (absences.length > 0) {
      html += '<tr><td class="row-label" style="color:var(--muted);"><i class="fas fa-plane-departure" style="font-size:10px;margin-right:3px;"></i>Отпуск / Ком.</td>';
      for (var m = 1; m <= 12; m++) {
        var info = absMonths[m];
        if (info) {
          var marks = '';
          if (info.vac) marks += '<span class="an-abs-mark an-abs-vac"></span>';
          if (info.trip) marks += '<span class="an-abs-mark an-abs-trip"></span>';
          var bgCls = info.vac && info.trip ? 'an-cell-vac an-cell-trip' : (info.vac ? 'an-cell-vac' : 'an-cell-trip');
          html += '<td class="' + bgCls + '" title="' + esc(info.titles.join('; ')) + '">' + marks + '</td>';
        } else {
          html += '<td></td>';
        }
      }
      html += '<td></td></tr>';
    }

    html += '</tbody></table></div></div>';
  }

  // Таблица задач
  html += '<div class="rpt-tasks-wrap">';
  html += '<div class="rpt-tasks-header">';
  html += '<div class="rpt-tasks-title"><i class="fas fa-tasks"></i> Задачи (' + tasks.length + ')';
  html += '<span class="an-legend"><span class="an-active-mark"></span> период';
  html += ' &nbsp; <span class="an-abs-mark an-abs-vac"></span> отпуск';
  html += ' &nbsp; <span class="an-abs-mark an-abs-trip"></span> командировка</span>';
  html += '</div>';
  html += '<div class="rpt-export-bar" id="anExportInline"></div>';
  html += '</div>';

  html += renderTasksTableBody(data);
  html += '</div>';

  el.innerHTML = html;
  _buildExport('anExportContainer', 'Отчёт_' + (emp.name || '').replace(/\s+/g, '_'), _taskExportCols());
}

/* ═══════════════════════════════════════════════════════════════════════
   ОБЩИЕ КОМПОНЕНТЫ
   ═══════════════════════════════════════════════════════════════════════ */

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
  } else if (data.view === 'all') {
    var depts = data.depts || [];
    html += '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' + depts.length + '</div><div class="an-summary-label">Отделов</div></div>';
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
    var monthMap = {};
    months.forEach(function(md) { monthMap[md.month] = md; });
    for (var m = 1; m <= 12; m++) {
      var planned = monthMap[m] ? monthMap[m].planned : 0;
      html += '<td class="cell-num">' + (planned > 0 ? planned.toFixed(1) : '') + '</td>';
    }

    html += '<td class="cell-num"><strong>' + fmtHrs(e.total_planned) + '</strong></td>';
    html += '<td class="cell-num"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(e.total_load_pct) + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table></div></div>';
  return html;
}

/* Таблица сотрудников для табличного режима */
function _renderEmpTable(employees, title) {
  if (!employees || !employees.length) return '';
  var html = '<div class="rpt-tasks-wrap" style="margin-top:16px;">';
  if (title) {
    html += '<div class="rpt-tasks-header"><div class="rpt-tasks-title"><i class="fas fa-users"></i> ' + title + '</div></div>';
  }
  html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
  html += '<table class="an-list-table">';
  html += '<colgroup><col style="width:140px;">';
  for (var m = 1; m <= 12; m++) html += '<col style="width:56px;">';
  html += '<col style="width:64px;"><col style="width:68px;">';
  html += '</colgroup>';
  html += '<thead><tr>';
  html += '<th>Сотрудник</th>';
  for (var m = 1; m <= 12; m++) html += '<th class="cell-num" style="font-size:10px;">' + MONTHS_RU[m-1] + '</th>';
  html += '<th class="cell-num">Итого</th><th class="cell-num">Загрузка</th>';
  html += '</tr></thead><tbody>';

  employees.forEach(function(e) {
    var badgeCls = loadBadgeCls(e.total_load_pct);
    html += '<tr onclick="anDrillEmployee(' + e.id + ')">';
    html += '<td><strong>' + esc(e.name) + '</strong></td>';
    var monthMap = {};
    (e.months || []).forEach(function(md) { monthMap[md.month] = md; });
    for (var m = 1; m <= 12; m++) {
      var planned = monthMap[m] ? monthMap[m].planned : 0;
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

  months.forEach(function(m) {
    var badgeCls = loadBadgeCls(m.load_pct);
    html += '<tr>';
    html += '<td class="row-label">' + MONTHS_RU[(m.month || 1) - 1] + '</td>';
    html += '<td>' + fmtHrs(m.planned) + '</td>';
    html += '<td>' + fmtHrs(m.norm) + '</td>';
    html += '<td><span class="an-load-badge ' + badgeCls + '">' + fmtPct(m.load_pct) + '</span></td>';
    html += '</tr>';
  });

  html += '</tbody></table>';
  return html;
}

/* Блок задач для графического режима (employee view) */
function renderTasksBlock(data) {
  var tasks = data.tasks || [];
  var html = '<div class="an-widget an-widget-full" style="padding:0;">';
  html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-tasks"></i> Задачи (' + tasks.length + ')';
  html += '<span class="an-legend"><span class="an-active-mark"></span> период выполнения';
  html += ' &nbsp; <span class="an-abs-mark an-abs-vac"></span> отпуск';
  html += ' &nbsp; <span class="an-abs-mark an-abs-trip"></span> командировка</span>';
  html += '</div>';

  html += renderTasksTableBody(data);
  html += '</div>';
  return html;
}

/* Общее тело таблицы задач (используется в обоих режимах) */
function renderTasksTableBody(data) {
  var tasks = data.tasks || [];
  var selYears = idsToList(currentYears);

  if (tasks.length === 0) {
    return '<div class="an-empty"><i class="fas fa-clipboard-check"></i>Нет задач</div>';
  }

  var absences = data.absences || [];
  var absMonths = {};
  absences.forEach(function(a) {
    var dsLabel = a.date_start ? a.date_start.slice(8,10) + '.' + a.date_start.slice(5,7) : '';
    var deLabel = a.date_end ? a.date_end.slice(8,10) + '.' + a.date_end.slice(5,7) : '';
    var fullLabel = a.label + ': ' + dsLabel + ' – ' + deLabel;
    selYears.forEach(function(y) {
      var yInt = parseInt(y);
      var ds = new Date(a.date_start);
      var de = new Date(a.date_end);
      for (var mm = 1; mm <= 12; mm++) {
        var mStart = new Date(yInt, mm - 1, 1);
        var mEnd = new Date(yInt, mm, 0);
        if (mEnd >= ds && mStart <= de) {
          if (!absMonths[mm]) absMonths[mm] = {vac: false, trip: false, titles: []};
          if (a.type === 'vacation') absMonths[mm].vac = true;
          else absMonths[mm].trip = true;
          if (absMonths[mm].titles.indexOf(fullLabel) === -1) absMonths[mm].titles.push(fullLabel);
        }
      }
    });
  });

  var html = '<div style="overflow-x:auto;padding:0 20px 20px;">';
  html += '<table class="an-tasks-table"><thead><tr>';
  html += '<th>Название</th><th>Проект</th><th>Начало</th><th>Окончание</th>';
  for (var m = 1; m <= 12; m++) {
    html += '<th class="cell-num" style="font-size:10px;" title="Плановые часы / период выполнения задачи">' + MONTHS_RU[m-1] + '</th>';
  }
  html += '<th class="cell-num">Итого (ч)</th><th>Статус</th>';
  html += '</tr></thead><tbody>';

  if (absences.length > 0) {
    html += '<tr class="an-absence-row">';
    html += '<td colspan="4" style="font-weight:600;color:var(--muted);font-size:12px;"><i class="fas fa-plane-departure" style="margin-right:4px;"></i>Отпуска / командировки</td>';
    for (var m = 1; m <= 12; m++) {
      var info = absMonths[m];
      if (info) {
        var marks = '';
        if (info.vac) marks += '<span class="an-abs-mark an-abs-vac"></span>';
        if (info.trip) marks += '<span class="an-abs-mark an-abs-trip"></span>';
        var bgCls = info.vac ? 'an-cell-vac' : 'an-cell-trip';
        html += '<td class="cell-num ' + bgCls + '" title="' + esc(info.titles.join('; ')) + '">' + marks + '</td>';
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

    var activeMonths = {};
    if (t.date_start) {
      selYears.forEach(function(y) {
        var yInt = parseInt(y);
        var ds = new Date(t.date_start);
        var de = t.date_end ? new Date(t.date_end) : null;
        for (var mm = 1; mm <= 12; mm++) {
          var mStart = new Date(yInt, mm - 1, 1);
          var mEnd = new Date(yInt, mm, 0);
          if (mEnd >= ds && (!de || mStart <= de)) activeMonths[mm] = true;
        }
      });
    }

    html += '<tr>';
    html += '<td>' + esc(t.work_name) + '</td>';
    html += '<td>' + esc(t.project_name || t.project) + '</td>';
    html += '<td style="white-space:nowrap">' + dsF + '</td>';
    html += '<td style="white-space:nowrap">' + deF + '</td>';

    var rowTotal = 0;
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
      var absInfo = absMonths[m];
      var absCls = absInfo ? (absInfo.vac && absInfo.trip ? ' an-cell-vac an-cell-trip' : (absInfo.vac ? ' an-cell-vac' : ' an-cell-trip')) : '';
      var absTitle = absInfo ? ' title="' + esc(absInfo.titles.join('; ')) + '"' : '';
      if (hrs > 0) {
        html += '<td class="cell-num' + absCls + '"' + absTitle + '>' + hrs.toFixed(1) + '</td>';
      } else if (!hasPlanHours && activeMonths[m]) {
        html += '<td class="cell-num' + absCls + '"' + absTitle + '><span class="an-active-mark" title="Период выполнения"></span></td>';
      } else {
        html += '<td class="cell-num' + absCls + '"' + absTitle + '></td>';
      }
    }
    html += '<td class="cell-num"><strong>' + (rowTotal > 0 ? rowTotal.toFixed(1) : '') + '</strong></td>';
    html += '<td><span class="' + statusCls + '">' + statusText + '</span></td>';
    html += '</tr>';
  });
  html += '</tbody></table></div>';
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

/* ── Экспорт ──────────────────────────────────────────────────────────── */
function _deptExportCols() {
  return [
    { key: 'dept_code', header: 'Код отдела', width: 80, forceText: true },
    { key: 'dept_name', header: 'Название', width: 200 },
    { key: 'employees', header: 'Сотрудников', width: 100 },
    { key: 'planned', header: 'План (ч)', width: 100 },
    { key: 'norm', header: 'Норма (ч)', width: 100 },
    { key: 'load_pct', header: 'Загрузка (%)', width: 100, format: function(r) { return r.load_pct.toFixed(1); } }
  ];
}

function _empExportRow(e, deptCode, sectorName) {
  var row = {
    dept: deptCode, sector: sectorName, name: e.name,
    planned: e.total_planned || 0, norm: e.total_norm || 0,
    load_pct: e.total_load_pct || 0
  };
  var monthMap = {};
  (e.months || []).forEach(function(md) { monthMap[md.month] = md; });
  for (var m = 1; m <= 12; m++) {
    row['m' + m] = monthMap[m] ? monthMap[m].planned : 0;
  }
  return row;
}

function _empExportCols() {
  var cols = [
    { key: 'dept', header: 'Отдел', width: 80, forceText: true },
    { key: 'sector', header: 'Сектор', width: 120 },
    { key: 'name', header: 'Сотрудник', width: 180 }
  ];
  for (var m = 1; m <= 12; m++) {
    cols.push({ key: 'm' + m, header: MONTHS_RU[m-1], width: 60 });
  }
  cols.push({ key: 'planned', header: 'Итого (ч)', width: 80 });
  cols.push({ key: 'load_pct', header: 'Загрузка (%)', width: 80, format: function(r) { return r.load_pct.toFixed(1); } });
  return cols;
}

function _taskExportCols() {
  var cols = [
    { key: 'work_name', header: 'Название', width: 240 },
    { key: 'project', header: 'Проект', width: 140 },
    { key: 'date_start', header: 'Начало', width: 100 },
    { key: 'date_end', header: 'Окончание', width: 100 }
  ];
  for (var m = 1; m <= 12; m++) {
    cols.push({ key: 'm' + m, header: MONTHS_RU[m-1], width: 60 });
  }
  cols.push({ key: 'total_hours', header: 'Итого (ч)', width: 80 });
  cols.push({ key: 'status', header: 'Статус', width: 80 });
  return cols;
}

function _buildExport(containerId, pageName, columns) {
  // Всегда рендерим в верхнюю панель
  var targetId = 'anExportTop';
  var container = document.getElementById(targetId);
  if (!container || typeof buildExportDropdown !== 'function') return;
  container.innerHTML = '';
  buildExportDropdown(targetId, {
    pageName: pageName,
    columns: columns,
    getAllData: function() { return _exportData; },
    getFilteredData: function() { return _exportData; }
  });
}

/* ── Init ─────────────────────────────────────────────────────────────── */
loadData();

})();
