/**
 * dashboard.js — Личный план сотрудника / сводка для руководителя.
 */
(function() {
'use strict';

var cfg = JSON.parse(document.getElementById('dash-config').textContent);
var currentYear = cfg.currentYear;
var currentMonth = cfg.currentMonth;
var lastData = null;

var MONTHS_RU = ['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
var MONTHS_FULL = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                   'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];

/* ── Утилиты ─────────────────────────────────────────────────────── */
function esc(s) {
  if (!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function loadBadgeCls(pct) {
  if (pct <= 85) return 'ok';
  if (pct <= 100) return 'warn';
  return 'over';
}

function fmtPct(v) { return v > 0 ? v.toFixed(1) + '%' : '0%'; }
function fmtHrs(v) { return v > 0 ? v.toFixed(1) : '0'; }
function fmtDate(iso) {
  if (!iso) return '—';
  return iso.slice(8,10) + '.' + iso.slice(5,7) + '.' + iso.slice(0,4);
}

/* ── API ─────────────────────────────────────────────────────────── */
function loadDashboard() {
  fetch('/api/dashboard/?year=' + currentYear + '&month=' + currentMonth)
  .then(function(r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(function(data) {
    if (data.error) {
      document.getElementById('dashKPI').innerHTML =
        '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> ' + esc(data.error) + '</div>';
      return;
    }
    lastData = data;
    var isLeader = data.role && data.role !== 'user';
    renderMonthChips(data.available_years || [currentYear]);
    renderHeroSub(data);
    renderKPI(data.kpi);
    renderTeam(data.team);
    renderTasks(data.tasks, isLeader);
    renderDebts(data.debts, isLeader);
    renderDoneLate(data.done_late, isLeader);
  })
  .catch(function(e) {
    console.error('Dashboard error:', e);
    document.getElementById('dashKPI').innerHTML =
      '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> Ошибка загрузки</div>';
  });
}

/* ── Переключение года / месяца ───────────────────────────────────── */
window.dashSetYear = function(y) {
  currentYear = y;
  loadDashboard();
};

window.dashSetMonth = function(m) {
  currentMonth = m;
  loadDashboard();
};

/* ── Чипы месяцев + навигация по году ─────────────────────────────── */
function renderMonthChips(years) {
  var html = '<div class="an-toolbar-panel">';
  // Навигация по году (◀ год ▶)
  if (years && years.length > 1) {
    html += '<div class="dash-year-nav">';
    var idx = years.indexOf(currentYear);
    var canPrev = idx > 0;
    var canNext = idx < years.length - 1;
    html += '<button' + (canPrev ? ' onclick="dashSetYear(' + years[idx-1] + ')"' : ' disabled style="opacity:0.3;cursor:default;"') + '><i class="fas fa-chevron-left"></i></button>';
    html += '<span class="dash-year-label">' + currentYear + '</span>';
    html += '<button' + (canNext ? ' onclick="dashSetYear(' + years[idx+1] + ')"' : ' disabled style="opacity:0.3;cursor:default;"') + '><i class="fas fa-chevron-right"></i></button>';
    html += '</div>';
  } else {
    html += '<span class="dash-year-label" style="margin-right:12px;">' + currentYear + '</span>';
  }
  // Чипы месяцев
  html += '<div class="an-chips">';
  for (var m = 1; m <= 12; m++) {
    var cls = m === currentMonth ? 'an-chip active' : 'an-chip';
    html += '<button class="' + cls + '" onclick="dashSetMonth(' + m + ')">' + MONTHS_RU[m-1] + '</button>';
  }
  html += '</div></div>';
  document.getElementById('dashMonthChips').innerHTML = html;
}

/* ── Hero subtitle ───────────────────────────────────────────────── */
function scopeLabel(data) {
  var r = data.role;
  if (r === 'admin' || r === 'ntc_head' || r === 'ntc_deputy') return 'НТЦ';
  if (r === 'dept_head' || r === 'dept_deputy') return 'Отдел ' + (data.employee.dept || '');
  if (r === 'sector_head') return 'Сектор ' + (data.employee.sector || '');
  return '';
}

function renderHeroSub(data) {
  var el = document.getElementById('dashHeroSub');
  var kpi = data.kpi;
  var parts = [];
  var scope = scopeLabel(data);
  if (scope) parts.push('<span style="opacity:0.75;">' + scope + '</span>');

  if (kpi.total_debts > 0) {
    parts.push('<span style="background:rgba(239,68,68,0.25);padding:2px 10px;border-radius:8px;font-weight:600;">' +
      '<i class="fas fa-exclamation-circle"></i> Долги: ' + kpi.total_debts + '</span>');
  }
  if (kpi.inwork_count > 0) {
    parts.push('<span style="background:rgba(245,158,11,0.25);padding:2px 10px;border-radius:8px;font-weight:600;">' +
      '<i class="fas fa-clock"></i> В работе: ' + kpi.inwork_count + '</span>');
  }
  if (kpi.total_debts === 0 && kpi.inwork_count === 0) {
    parts.push('<span style="opacity:0.75;">Все задачи в порядке <i class="fas fa-check-circle"></i></span>');
  }

  el.innerHTML = MONTHS_FULL[currentMonth - 1] + ' ' + currentYear + ' &nbsp; ' + parts.join(' ');
}

/* ── KPI-карточки ────────────────────────────────────────────────── */
function renderKPI(kpi) {
  var loadCls = loadBadgeCls(kpi.load_pct);
  var colorMap = {ok: 'an-val-green', warn: 'an-val-yellow', over: 'an-val-red'};

  var cards = [
    { val: fmtPct(kpi.load_pct), label: 'Загрузка', cls: colorMap[loadCls] || '' },
    { val: fmtHrs(kpi.planned_hours) + ' / ' + fmtHrs(kpi.norm_hours), label: 'План / Норма (ч)', cls: 'an-val-accent' },
    { val: kpi.done_count, label: 'Выполнено', cls: 'an-val-green' },
    { val: kpi.inwork_count, label: 'В работе', cls: 'an-val-accent' },
    { val: kpi.total_debts, label: 'Долги', cls: kpi.total_debts > 0 ? 'an-val-red' : 'an-val-green' },
  ];

  // % в срок — только если всего выполнено >= 3 (при 1-2 метрика не информативна)
  if (kpi.on_time_pct >= 0 && (kpi.total_done || 0) >= 3) {
    cards.push({ val: fmtPct(kpi.on_time_pct), label: '% в срок', cls: kpi.on_time_pct >= 90 ? 'an-val-green' : (kpi.on_time_pct >= 70 ? 'an-val-yellow' : 'an-val-red') });
  }

  if (kpi.avg_overdue_days > 0 && kpi.total_debts > 0) {
    cards.push({ val: kpi.avg_overdue_days + ' дн.', label: 'Ср. просрочка', cls: 'an-val-red' });
  }

  var html = '';
  cards.forEach(function(c) {
    html += '<div class="an-summary-card">';
    html += '<div class="an-summary-val ' + c.cls + '">' + c.val + '</div>';
    html += '<div class="an-summary-label">' + c.label + '</div>';
    html += '</div>';
  });
  document.getElementById('dashKPI').innerHTML = html;
}

/* ── Команда: отделы → сектора → сотрудники (с задачами) ────────── */
function renderTeam(team) {
  var el = document.getElementById('dashTeam');
  if (!team || !team.departments || !team.departments.length) {
    el.innerHTML = '';
    return;
  }

  var html = '<div class="dash-section">';
  html += '<div class="dash-section-title" onclick="dashToggle(this)">';
  html += '<i class="fas fa-users"></i> Команда (' + team.total_employees + ')';
  html += ' &nbsp; <span class="an-load-badge ' + loadBadgeCls(team.avg_load_pct) + '">' + fmtPct(team.avg_load_pct) + ' ср.загрузка</span>';
  if (team.total_overdue > 0) {
    html += ' &nbsp; <span class="an-load-badge over">' + team.total_overdue + ' просроч.</span>';
  }
  html += '<i class="fas fa-chevron-down dash-toggle collapsed"></i>';
  html += '</div>';

  html += '<div class="dash-section-body collapsed">';

  team.departments.forEach(function(dept) {
    html += '<div class="dash-dept">';
    html += '<div class="dash-dept-header" onclick="dashToggleDept(this)">';
    html += '<i class="fas fa-chevron-right dash-dept-toggle"></i>';
    html += '<strong>' + esc(dept.code) + '</strong>';
    if (dept.name) html += ' <span class="dash-dept-name">' + esc(dept.name) + '</span>';
    html += ' <span class="dash-dept-meta">' + dept.count + ' чел.';
    html += ' &middot; ' + fmtPct(dept.avg_load_pct) + ' загр.';
    if (dept.overdue_count > 0) {
      html += ' &middot; <span class="an-load-badge over" style="font-size:11px;">' + dept.overdue_count + ' просроч.</span>';
    }
    html += '</span>';
    html += '</div>';

    html += '<div class="dash-dept-body" style="display:none;">';

    dept.sectors.forEach(function(sector) {
      html += '<div class="dash-sector">';
      html += '<div class="dash-sector-header">';
      html += '<i class="fas fa-layer-group" style="color:var(--accent);font-size:12px;"></i> ';
      html += '<strong>' + esc(sector.name) + '</strong>';
      html += ' <span class="dash-dept-meta">' + sector.count + ' чел.';
      html += ' &middot; ' + fmtPct(sector.avg_load_pct) + ' загр.';
      if (sector.overdue_count > 0) {
        html += ' &middot; <span class="an-load-badge over" style="font-size:11px;">' + sector.overdue_count + ' просроч.</span>';
      }
      html += '</span>';
      html += '</div>';

      // Сотрудники сектора — каждый как dropdown
      sector.employees.forEach(function(e) {
        html += _renderEmployeeDropdown(e);
      });

      html += '</div>'; // dash-sector
    });

    html += '</div>'; // dash-dept-body
    html += '</div>'; // dash-dept
  });

  html += '</div></div>'; // dash-section-body, dash-section
  el.innerHTML = html;
}

/* ── Dropdown сотрудника (задачи + долги) ────────────────────────── */
function _renderEmployeeDropdown(e) {
  var badgeCls = loadBadgeCls(e.load_pct);
  var hasTasks = e.tasks && e.tasks.length > 0;
  var hasDebts = e.debts && e.debts.length > 0;
  var hasContent = hasTasks || hasDebts;

  var html = '<div class="dash-emp">';

  // Заголовок сотрудника — компактная строка
  html += '<div class="dash-emp-header' + (hasContent ? ' clickable' : '') + '"';
  if (hasContent) html += ' onclick="dashToggleEmp(this)"';
  html += '>';
  if (hasContent) {
    html += '<i class="fas fa-chevron-right dash-emp-toggle"></i>';
  } else {
    html += '<span style="width:12px;display:inline-block;"></span>';
  }
  html += '<span class="dash-emp-name">' + esc(e.name) + '</span>';
  html += '<span class="dash-emp-load"><span class="an-load-badge ' + badgeCls + '">' + fmtPct(e.load_pct) + '</span></span>';
  html += '<span class="dash-emp-hrs">' + fmtHrs(e.planned) + ' ч</span>';
  html += '<span class="dash-emp-tag' + (e.done_count > 0 ? ' done' : '') + '">' + (e.done_count > 0 ? e.done_count + ' выполн.' : '') + '</span>';
  html += '<span class="dash-emp-tag">' + (e.inwork_count > 0 ? e.inwork_count + ' в работе' : '') + '</span>';
  html += '<span class="dash-emp-tag' + (e.overdue_count > 0 ? ' debt' : '') + '">' + (e.overdue_count > 0 ? e.overdue_count + ' долг.' : '') + '</span>';
  html += '</div>';

  // Тело — компактный список задач и долгов
  if (hasContent) {
    html += '<div class="dash-emp-body" style="display:none;">';

    if (hasTasks) {
      html += '<div class="dash-emp-label"><i class="fas fa-tasks"></i> ' + MONTHS_FULL[currentMonth - 1] + '</div>';
      html += _renderCompactList(e.tasks);
    }

    if (hasDebts) {
      html += '<div class="dash-emp-label debt"><i class="fas fa-exclamation-triangle"></i> Долги</div>';
      html += _renderCompactList(e.debts);
    }

    html += '</div>';
  }

  html += '</div>';
  return html;
}

/* ── Компактный список задач (для dropdown сотрудника) ───────────── */
function _renderCompactList(tasks) {
  var html = '<ul class="dash-compact-list">';
  tasks.forEach(function(t) {
    var statusCls = 'an-badge-status an-badge-' + t.status;
    var statusText = t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просроч.' : 'В работе');
    var badge = '';
    if (t.days_overdue) badge = '<span class="dash-days-badge dash-days-overdue">' + t.days_overdue + ' дн.</span>';
    else if (t.days_left !== undefined && t.days_left >= 0) badge = '<span class="dash-days-badge dash-days-left">' + t.days_left + ' дн.</span>';
    else if (t.days_late) badge = '<span class="dash-days-badge dash-days-late">+' + t.days_late + ' дн.</span>';

    html += '<li>';
    html += '<span class="dcl-name">' + esc(t.work_name) + '</span>';
    if (t.project_name) html += '<span class="dcl-project">' + esc(t.project_name) + '</span>';
    html += '<span class="dcl-date">' + fmtDate(t.date_end) + '</span>';
    html += '<span class="' + statusCls + '">' + statusText + '</span>';
    if (badge) html += badge;
    html += '</li>';
  });
  html += '</ul>';
  return html;
}

/* ── Задачи текущего месяца ──────────────────────────────────────── */
function renderTasks(tasks, showExecutor) {
  var el = document.getElementById('dashTasks');
  if (!tasks || !tasks.length) {
    el.innerHTML = '<div class="dash-section"><div class="dash-section-title"><i class="fas fa-tasks"></i> Задачи — ' +
      MONTHS_FULL[currentMonth - 1] + '</div><div class="an-empty"><i class="fas fa-clipboard-check"></i>Нет задач на этот месяц</div></div>';
    return;
  }

  var html = '<div class="dash-section">';
  html += '<div class="dash-section-title" onclick="dashToggle(this)">';
  html += '<i class="fas fa-tasks"></i> Задачи — ' + MONTHS_FULL[currentMonth - 1] + ' (' + tasks.length + ')';
  html += '<i class="fas fa-chevron-down dash-toggle collapsed"></i>';
  html += '</div>';

  html += '<div class="dash-section-body collapsed">';
  html += _renderTasksTable(tasks, showExecutor);
  html += '</div></div>';
  el.innerHTML = html;
}

/* ── Долги ────────────────────────────────────────────────────────── */
function renderDebts(debts, showExecutor) {
  var el = document.getElementById('dashDebts');
  if (!debts || !debts.length) {
    el.innerHTML = '';
    return;
  }

  var html = '<div class="dash-section">';
  html += '<div class="dash-section-title" onclick="dashToggle(this)">';
  html += '<i class="fas fa-exclamation-triangle" style="color:var(--danger)"></i> Долги — просроченные задачи (' + debts.length + ')';
  html += '<i class="fas fa-chevron-down dash-toggle collapsed"></i>';
  html += '</div>';

  html += '<div class="dash-section-body collapsed">';
  html += _renderTasksTable(debts, showExecutor);
  html += '</div></div>';
  el.innerHTML = html;
}

/* ── Выполнены с просрочкой ──────────────────────────────────────── */
function renderDoneLate(items, showExecutor) {
  var el = document.getElementById('dashDoneLate');
  if (!items || !items.length) {
    el.innerHTML = '';
    return;
  }

  var html = '<div class="dash-section">';
  html += '<div class="dash-section-title" onclick="dashToggle(this)">';
  html += '<i class="fas fa-clock" style="color:#d97706"></i> Выполнены с просрочкой (' + items.length + ')';
  html += '<i class="fas fa-chevron-down dash-toggle collapsed"></i>';
  html += '</div>';

  html += '<div class="dash-section-body collapsed">';
  html += _renderTasksTable(items, showExecutor);
  html += '</div></div>';
  el.innerHTML = html;
}

/* ── Общая таблица задач ─────────────────────────────────────────── */
function _renderTasksTable(tasks, showExecutor) {
  var html = '<div style="overflow-x:auto;">';
  html += '<table class="dash-tasks-table"><thead><tr>';
  html += '<th>Задача</th><th>Проект</th>';
  if (showExecutor) html += '<th>Исполнитель</th>';
  html += '<th>Срок</th><th>Статус</th><th></th>';
  html += '</tr></thead><tbody>';

  tasks.forEach(function(t) {
    var statusCls = 'an-badge-status an-badge-' + t.status;
    var statusText = t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просроч.' : 'В работе');

    html += '<tr>';
    html += '<td>' + esc(t.work_name) + '</td>';
    html += '<td>' + esc(t.project_name) + '</td>';
    if (showExecutor) html += '<td>' + esc(t.executor_name || '') + '</td>';
    html += '<td style="white-space:nowrap">' + fmtDate(t.date_end) + '</td>';
    html += '<td><span class="' + statusCls + '">' + statusText + '</span></td>';
    html += '<td>';
    if (t.days_overdue) {
      html += '<span class="dash-days-badge dash-days-overdue">' + t.days_overdue + ' дн.</span>';
    } else if (t.days_left !== undefined && t.days_left >= 0) {
      html += '<span class="dash-days-badge dash-days-left">' + t.days_left + ' дн.</span>';
    } else if (t.days_late) {
      html += '<span class="dash-days-badge dash-days-late">+' + t.days_late + ' дн.</span>';
    }
    html += '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  return html;
}

/* ── Сворачивание секций ─────────────────────────────────────────── */
window.dashToggle = function(titleEl) {
  var body = titleEl.nextElementSibling;
  var toggle = titleEl.querySelector('.dash-toggle');
  if (body) body.classList.toggle('collapsed');
  if (toggle) toggle.classList.toggle('collapsed');
};

/* ── Сворачивание отделов ────────────────────────────────────────── */
window.dashToggleDept = function(headerEl) {
  var body = headerEl.nextElementSibling;
  var toggle = headerEl.querySelector('.dash-dept-toggle');
  if (!body) return;
  var isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.classList.toggle('open', !isOpen);
};

/* ── Сворачивание сотрудника ─────────────────────────────────────── */
window.dashToggleEmp = function(headerEl) {
  var body = headerEl.nextElementSibling;
  var toggle = headerEl.querySelector('.dash-emp-toggle');
  if (!body) return;
  var isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.classList.toggle('open', !isOpen);
};

/* ── Init ─────────────────────────────────────────────────────────── */
loadDashboard();

})();
