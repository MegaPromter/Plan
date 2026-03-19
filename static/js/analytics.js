/**
 * analytics.js — Единый модуль аналитики «Личный план».
 * Иерархический drill-down: все отделы → отдел → сектор → сотрудник.
 */
(function() {
'use strict';

/* ── Конфигурация из шаблона ──────────────────────────────────────────── */
var cfg = JSON.parse(document.getElementById('an-config').textContent);
var currentYear  = cfg.currentYear;
var currentMonth = 0;      // 0 = все месяцы
var currentProjectId = 0;
var currentDept  = '';      // код отдела
var currentSectorId = 0;
var currentExecutorId = 0;

var MONTHS_RU = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
var MONTHS_FULL = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                   'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];

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

/* ── API ─────────────────────────────────────────────────────────────── */
function buildUrl() {
  var u = '/api/analytics/plan/?year=' + currentYear;
  if (currentMonth) u += '&month=' + currentMonth;
  if (currentProjectId) u += '&project_id=' + currentProjectId;
  if (currentDept) u += '&dept=' + encodeURIComponent(currentDept);
  if (currentSectorId) u += '&sector_id=' + currentSectorId;
  if (currentExecutorId) u += '&executor_id=' + currentExecutorId;
  return u;
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

/* ── Навигация ───────────────────────────────────────────────────────── */
window.anSetYear = function(y) {
  currentYear = y;
  loadData();
};

window.anSetMonth = function(m) {
  currentMonth = currentMonth === m ? 0 : m;
  loadData();
};

window.anSetProject = function(id) {
  currentProjectId = currentProjectId === id ? 0 : id;
  loadData();
};

window.anDrillDept = function(code) {
  currentDept = code;
  currentSectorId = 0;
  currentExecutorId = 0;
  loadData();
};

window.anDrillSector = function(id) {
  currentSectorId = id;
  currentExecutorId = 0;
  loadData();
};

window.anDrillEmployee = function(id) {
  currentExecutorId = id;
  loadData();
};

window.anGoHome = function() {
  currentDept = '';
  currentSectorId = 0;
  currentExecutorId = 0;
  loadData();
};

window.anGoDept = function(code) {
  currentDept = code || '';
  currentSectorId = 0;
  currentExecutorId = 0;
  loadData();
};

/* ── Тулбар ──────────────────────────────────────────────────────────── */
function renderToolbar(data) {
  var tb = document.getElementById('anToolbar');
  var html = '';

  // Год
  html += '<span class="an-toolbar-label">Год:</span><div class="an-chips">';
  (data.years || []).forEach(function(y) {
    var cls = y === currentYear ? 'an-chip active' : 'an-chip';
    html += '<button class="' + cls + '" onclick="anSetYear(' + y + ')">' + y + '</button>';
  });
  html += '</div>';

  // Месяц
  html += '<div class="an-toolbar-sep"></div><span class="an-toolbar-label">Месяц:</span><div class="an-chips">';
  for (var m = 1; m <= 12; m++) {
    var cls = m === currentMonth ? 'an-chip active' : 'an-chip';
    html += '<button class="' + cls + '" onclick="anSetMonth(' + m + ')">' + MONTHS_RU[m-1] + '</button>';
  }
  if (currentMonth) {
    html += '<button class="an-chip-clear" onclick="anSetMonth(0)">сбросить</button>';
  }
  html += '</div>';

  // Проекты
  var projects = data.nav_projects || [];
  if (projects.length > 0) {
    html += '<div class="an-toolbar-sep"></div><span class="an-toolbar-label">Проект:</span><div class="an-chips">';
    projects.forEach(function(p) {
      var cls = p.id === currentProjectId ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anSetProject(' + p.id + ')">' + esc(p.name) + '</button>';
    });
    if (currentProjectId) {
      html += '<button class="an-chip-clear" onclick="anSetProject(0)">сбросить</button>';
    }
    html += '</div>';
  }

  // Отделы (для admin/ntc)
  var depts = data.nav_depts || [];
  if (depts.length > 0 && data.view === 'all') {
    html += '<div class="an-toolbar-sep"></div><span class="an-toolbar-label">Отдел:</span><div class="an-chips">';
    depts.forEach(function(code) {
      html += '<button class="an-chip" onclick="anDrillDept(\'' + esc(code) + '\')">' + esc(code) + '</button>';
    });
    html += '</div>';
  }

  // Секторы (для dept_head или при drill-down в отдел)
  var sectors = data.nav_sectors || [];
  if (sectors.length > 0 && data.view === 'dept') {
    html += '<div class="an-toolbar-sep"></div><span class="an-toolbar-label">Сектор:</span><div class="an-chips">';
    sectors.forEach(function(s) {
      var cls = s.id === currentSectorId ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anDrillSector(' + s.id + ')">' + esc(s.name) + '</button>';
    });
    html += '</div>';
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
    if (currentDept || (data.role_info && (data.role_info.role === 'dept_head' || data.role_info.role === 'dept_deputy'))) {
      var deptCode = currentDept || data.role_info.dept;
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
  }

  bc.innerHTML = parts.join(' ');
}

/* ── Контент по типу view ────────────────────────────────────────────── */
function renderContent(data) {
  var el = document.getElementById('anContent');

  switch (data.view) {
    case 'all':      renderAllDepts(el, data); break;
    case 'dept':     renderDept(el, data); break;
    case 'sector':   renderSector(el, data); break;
    case 'employee': renderEmployee(el, data); break;
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

  // Графика загрузки
  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  // Таблица отделов
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

  // График
  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  // Секторы
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

  // Все сотрудники отдела (развёрнуто по секторам)
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

  // График
  html += '<div class="an-widgets">';
  html += '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
  html += '</div>';

  // Сотрудники
  html += renderEmployeesList(employees, 'Сотрудники сектора');

  el.innerHTML = html;
  renderBarChart(data.months || []);
}

/* ── View: сотрудник ─────────────────────────────────────────────────── */
function renderEmployee(el, data) {
  var html = renderSummaryCards(data);

  // График + таблица месяцев
  html += '<div class="an-widgets">';
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';

  // Таблица месяцев
  html += '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-calendar-alt"></i> Помесячная разбивка</div>';
  html += renderMonthsTable(data.months || []);
  html += '</div></div>';

  // Задачи
  var tasks = data.tasks || [];
  html += '<div class="an-widget an-widget-full" style="padding:0;">';
  html += '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-tasks"></i> Задачи (' + tasks.length + ')</div>';

  if (tasks.length === 0) {
    html += '<div class="an-empty"><i class="fas fa-clipboard-check"></i>Нет задач</div>';
  } else {
    html += '<div style="overflow-x:auto;padding:0 20px 20px;">';
    html += '<table class="an-tasks-table"><thead><tr>';
    html += '<th>Название</th><th>Проект</th><th>Дедлайн</th>';
    // Колонки по месяцам (сокращённые)
    for (var m = 1; m <= 12; m++) {
      html += '<th class="cell-num" style="font-size:10px;">' + MONTHS_RU[m-1] + '</th>';
    }
    html += '<th class="cell-num">Итого</th><th>Статус</th>';
    html += '</tr></thead><tbody>';

    tasks.forEach(function(t) {
      var dl = t.date_end ? t.date_end.slice(8,10) + '.' + t.date_end.slice(5,7) + '.' + t.date_end.slice(0,4) : '—';
      var statusCls = 'an-badge-status an-badge-' + t.status;
      var statusText = t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просроч.' : 'В работе');

      html += '<tr>';
      html += '<td>' + esc(t.work_name) + '</td>';
      html += '<td>' + esc(t.project || t.project_name) + '</td>';
      html += '<td>' + dl + '</td>';

      var rowTotal = 0;
      for (var m = 1; m <= 12; m++) {
        var key = currentYear + '-' + (m < 10 ? '0' + m : m);
        var hrs = (t.plan_hours && t.plan_hours[key]) ? parseFloat(t.plan_hours[key]) : 0;
        rowTotal += hrs;
        html += '<td class="cell-num">' + (hrs > 0 ? hrs.toFixed(1) : '') + '</td>';
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

  // Кол-во задач (для employee view)
  if (data.tasks) {
    var done = 0, overdue = 0;
    data.tasks.forEach(function(t) {
      if (t.status === 'done') done++;
      if (t.status === 'overdue') overdue++;
    });
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
