/**
 * dashboard.js — Личный план сотрудника / сводка для руководителя.
 */
(function() {
'use strict';

var cfg = JSON.parse(document.getElementById('dash-config').textContent);
var currentYear = cfg.currentYear;
var currentMonth = cfg.currentMonth;
var lastData = null;

// MONTHS_FULL, MONTHS_SHORT — в utils.js (1-based: MONTHS_FULL[1] = "Январь")

/* ── Утилиты — в utils.js (esc, loadBadgeCls, fmtPct, fmtHrs, fmtDate) ── */

/* ── Skeleton-заглушки для дашборда ──────────────────────────────── */
function _dashShowSkeletons() {
  var kpiEl = document.getElementById('dashKPI');
  if (kpiEl) {
    kpiEl.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;">' +
      '<div class="skeleton-card skeleton-shimmer"></div>'.repeat(4) +
      '</div>';
  }
  var tasksEl = document.getElementById('dashTasks');
  if (tasksEl) {
    tasksEl.innerHTML =
      '<div class="skeleton-card skeleton-shimmer skeleton-card-lg" style="margin-bottom:12px;"></div>';
  }
  var debtsEl = document.getElementById('dashDebts');
  if (debtsEl) {
    debtsEl.innerHTML =
      '<div class="skeleton-card skeleton-shimmer skeleton-card-lg" style="margin-bottom:12px;"></div>';
  }
}

/* ── API ─────────────────────────────────────────────────────────── */
function loadDashboard() {
  _dashShowSkeletons();
  fetch('/api/dashboard/?year=' + currentYear + '&month=' + currentMonth)
  .then(function(r) {
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  })
  .then(function(data) {
    if (data.error) {
      document.getElementById('dashKPI').innerHTML =
        emptyStateHtml({icon:'fas fa-exclamation-triangle', title: esc(data.error)});
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
      emptyStateHtml({icon:'fas fa-exclamation-triangle', title:'Ошибка загрузки', desc:'Попробуйте обновить страницу'});
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
    html += '<button class="' + cls + '" onclick="dashSetMonth(' + m + ')">' + MONTHS_SHORT[m] + '</button>';
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

  el.innerHTML = MONTHS_FULL[currentMonth] + ' ' + currentYear + ' &nbsp; ' + parts.join(' ');
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
  var widget = el.closest('.dash-widget');
  if (!team || !team.departments || !team.departments.length) {
    el.innerHTML = '';
    if (widget) widget.style.display = 'none';
    return;
  }
  if (widget) { widget.style.display = ''; _updateWidgetHeader(widget, '<i class="fas fa-users" style="color:var(--accent);margin-right:6px;"></i>Команда (' + team.total_employees + ') &nbsp; <span class="an-load-badge ' + loadBadgeCls(team.avg_load_pct) + '">' + fmtPct(team.avg_load_pct) + ' ср.загрузка</span>' + (team.total_overdue > 0 ? ' &nbsp; <span class="an-load-badge over">' + team.total_overdue + ' просроч.</span>' : '')); }

  var html = '';

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
  html += avatarHtml(e.name, 'sm') + ' ';
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
      html += '<div class="dash-emp-label"><i class="fas fa-tasks"></i> ' + MONTHS_FULL[currentMonth] + '</div>';
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
    if (t.work_designation) html += '<span class="dcl-designation">' + esc(t.work_designation) + '</span>';
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
  var widget = el.closest('.dash-widget');
  if (widget) _updateWidgetHeader(widget, '<i class="fas fa-tasks" style="color:var(--accent);margin-right:6px;"></i>Задачи — ' + MONTHS_FULL[currentMonth] + (tasks && tasks.length ? ' (' + tasks.length + ')' : ''));
  if (!tasks || !tasks.length) {
    el.innerHTML = emptyStateHtml({icon:'fas fa-clipboard-check', title:'Нет задач на этот месяц', desc:'Все задачи выполнены или ещё не запланированы', action:'<a class="btn btn-primary btn-sm" href="/plan/"><i class="fas fa-calendar-alt"></i> Перейти к плану</a>'});
    return;
  }

  el.innerHTML = _renderTasksTable(tasks, showExecutor);
}

/* ── Долги ────────────────────────────────────────────────────────── */
function renderDebts(debts, showExecutor) {
  var el = document.getElementById('dashDebts');
  var widget = el.closest('.dash-widget');
  if (!debts || !debts.length) {
    el.innerHTML = '';
    if (widget) widget.style.display = 'none';
    return;
  }
  if (widget) { widget.style.display = ''; _updateWidgetHeader(widget, '<i class="fas fa-exclamation-triangle" style="color:var(--danger);margin-right:6px;"></i>Долги — просроченные задачи (' + debts.length + ')'); }

  el.innerHTML = _renderTasksTable(debts, showExecutor);
}

/* ── Выполнены с просрочкой ──────────────────────────────────────── */
function renderDoneLate(items, showExecutor) {
  var el = document.getElementById('dashDoneLate');
  var widget = el.closest('.dash-widget');
  if (!items || !items.length) {
    el.innerHTML = '';
    if (widget) widget.style.display = 'none';
    return;
  }
  if (widget) { widget.style.display = ''; _updateWidgetHeader(widget, '<i class="fas fa-clock" style="color:#d97706;margin-right:6px;"></i>Выполнены с просрочкой (' + items.length + ')'); }

  el.innerHTML = _renderTasksTable(items, showExecutor);
}

/* ── Компактный список задач (основные секции) ─────────────────── */
function _renderTasksTable(tasks, showExecutor) {
  // Сортировка по проекту
  tasks = tasks.slice().sort(function(a, b) {
    var pa = (a.project_sort || a.project_name || '').toLowerCase();
    var pb = (b.project_sort || b.project_name || '').toLowerCase();
    return pa < pb ? -1 : pa > pb ? 1 : 0;
  });
  var html = '<ul class="dash-compact-list dash-section-list">';
  tasks.forEach(function(t) {
    var statusCls = 'an-badge-status an-badge-' + t.status;
    var statusText = t.status === 'done' ? 'Готово' : (t.status === 'overdue' ? 'Просроч.' : 'В работе');
    var badge = '';
    if (t.days_overdue) badge = '<span class="dash-days-badge dash-days-overdue">' + t.days_overdue + ' дн.</span>';
    else if (t.days_left !== undefined && t.days_left >= 0) badge = '<span class="dash-days-badge dash-days-left">' + t.days_left + ' дн.</span>';
    else if (t.days_late) badge = '<span class="dash-days-badge dash-days-late">+' + t.days_late + ' дн.</span>';

    html += '<li>';
    html += '<span class="dcl-name">' + esc(t.work_name) + '</span>';
    if (t.work_designation) html += '<span class="dcl-designation">' + esc(t.work_designation) + '</span>';
    if (t.project_name) html += '<span class="dcl-project">' + esc(t.project_name) + '</span>';
    if (showExecutor && t.executor_name) html += '<span class="dcl-executor">' + avatarHtml(t.executor_name, 'sm') + ' ' + esc(t.executor_name) + '</span>';
    html += '<span class="dcl-date">' + fmtDate(t.date_end) + '</span>';
    html += '<span class="' + statusCls + '">' + statusText + '</span>';
    if (badge) html += badge;
    html += '</li>';
  });
  html += '</ul>';
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

/* ── Обновление заголовка виджета ──────────────────────────────── */
function _updateWidgetHeader(widget, html) {
  var span = widget.querySelector('.dash-widget-header > span');
  if (span) span.innerHTML = html;
}

/* ── Dashboard Widget Customization ──────────────────────────────── */
var DASH_LAYOUT_KEY = 'dashboard_layout';

function getDashLayout() {
  try { return JSON.parse(localStorage.getItem(DASH_LAYOUT_KEY)); }
  catch(e) { return null; }
}

function saveDashLayout(layout) {
  localStorage.setItem(DASH_LAYOUT_KEY, JSON.stringify(layout));
}

window.toggleDashCustomize = function() {
  var grid = document.getElementById('dashGrid');
  grid.classList.toggle('customize-mode');
  var btn = document.getElementById('dashCustomizeBtn');
  if (grid.classList.contains('customize-mode')) {
    btn.innerHTML = '<i class="fas fa-check"></i> Готово';
    btn.classList.add('btn-primary');
    btn.classList.remove('btn-outline');
    // Show all widgets (including empty ones) so user can toggle visibility
    document.querySelectorAll('.dash-widget').forEach(function(w) {
      w.setAttribute('draggable', 'true');
    });
  } else {
    btn.innerHTML = '<i class="fas fa-th"></i> Настроить';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-outline');
    document.querySelectorAll('.dash-widget').forEach(function(w) {
      w.removeAttribute('draggable');
    });
    saveDashLayout(getCurrentLayout());
  }
};

window.toggleWidgetVisibility = function(btnEl) {
  var widget = btnEl.closest('.dash-widget');
  if (!widget) return;
  widget.classList.toggle('widget-hidden');
  var icon = btnEl.querySelector('i');
  if (widget.classList.contains('widget-hidden')) {
    icon.className = 'fas fa-eye-slash';
  } else {
    icon.className = 'fas fa-eye';
  }
};

function getCurrentLayout() {
  var widgets = document.querySelectorAll('.dash-widget');
  return Array.from(widgets).map(function(w, i) {
    return {
      id: w.dataset.widget,
      visible: !w.classList.contains('widget-hidden'),
      order: i
    };
  });
}

function applyDashLayout(layout) {
  if (!layout || !layout.length) return;
  var grid = document.getElementById('dashGrid');
  if (!grid) return;

  // Sort widgets by saved order
  var widgetMap = {};
  grid.querySelectorAll('.dash-widget').forEach(function(w) {
    widgetMap[w.dataset.widget] = w;
  });

  layout.sort(function(a, b) { return a.order - b.order; });

  layout.forEach(function(item) {
    var widget = widgetMap[item.id];
    if (!widget) return;
    grid.appendChild(widget); // re-appending reorders
    if (!item.visible) {
      widget.classList.add('widget-hidden');
      var icon = widget.querySelector('.dash-widget-toggle i');
      if (icon) icon.className = 'fas fa-eye-slash';
    } else {
      widget.classList.remove('widget-hidden');
    }
  });
}

/* ── Drag-and-drop for widgets in customize mode ─────────────────── */
function initWidgetDrag() {
  var grid = document.getElementById('dashGrid');
  if (!grid) return;
  var dragWidget = null;

  grid.addEventListener('dragstart', function(e) {
    if (!grid.classList.contains('customize-mode')) return;
    var widget = e.target.closest('.dash-widget');
    if (!widget) { e.preventDefault(); return; }
    dragWidget = widget;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', widget.dataset.widget);
    requestAnimationFrame(function() {
      if (dragWidget) dragWidget.classList.add('dragging-widget');
    });
  });

  grid.addEventListener('dragover', function(e) {
    if (!dragWidget) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    var target = e.target.closest('.dash-widget');
    if (!target || target === dragWidget) return;
    // Clear previous highlights
    grid.querySelectorAll('.drag-over-widget').forEach(function(w) {
      w.classList.remove('drag-over-widget');
    });
    target.classList.add('drag-over-widget');

    // Determine insert position
    var rect = target.getBoundingClientRect();
    var midY = rect.top + rect.height / 2;
    if (e.clientY < midY) {
      grid.insertBefore(dragWidget, target);
    } else {
      var next = target.nextElementSibling;
      if (next) grid.insertBefore(dragWidget, next);
      else grid.appendChild(dragWidget);
    }
  });

  grid.addEventListener('dragleave', function(e) {
    var target = e.target.closest('.dash-widget');
    if (target) target.classList.remove('drag-over-widget');
  });

  grid.addEventListener('drop', function(e) {
    e.preventDefault();
    cleanupDrag();
  });

  grid.addEventListener('dragend', function() {
    cleanupDrag();
  });

  function cleanupDrag() {
    if (dragWidget) {
      dragWidget.classList.remove('dragging-widget');
      dragWidget = null;
    }
    grid.querySelectorAll('.drag-over-widget').forEach(function(w) {
      w.classList.remove('drag-over-widget');
    });
  }
}

/* ── Init ─────────────────────────────────────────────────────────── */
loadDashboard();
applyDashLayout(getDashLayout());
initWidgetDrag();

})();
