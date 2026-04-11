/// <reference path="types.js" />
/**
 * dashboard.js — Личный план сотрудника / сводка для руководителя.
 *
 * Фичи:
 * 1. Цветные чипы месяцев (индикатор загрузки)
 * 2. Клик по KPI → раскрытие виджета
 * 3. «Показать все отделы» (скрытие без просрочек)
 * 4. Поиск по сотрудникам в команде
 * 5. Sparklines (мини-графики загрузки)
 * 6. «Мои задачи» для руководителя
 * 7. Экспорт долгов в CSV
 * 8. Auto-sync уведомлений при загрузке
 * 9. Сравнение с предыдущим месяцем (дельта в KPI)
 */
(function() {
'use strict';

/** @type {DashConfig} */
var cfg = JSON.parse(document.getElementById('dash-config').textContent);
/** @type {number} */
var currentYear = cfg.currentYear;
/** @type {number} */
var currentMonth = cfg.currentMonth;
/** @type {*} */
var lastData = null;

/* ── Skeleton-заглушки ──────────────────────────────────────────── */
function _dashShowSkeletons() {
  var kpiEl = document.getElementById('dashKPI');
  if (kpiEl) {
    kpiEl.innerHTML =
      '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;">' +
      '<div class="skeleton-card skeleton-shimmer"></div>'.repeat(4) +
      '</div>';
  }
}

/* ── API — основной запрос ──────────────────────────────────────── */
function loadDashboard() {
  _dashShowSkeletons();
  // Сбросить виджеты
  document.querySelectorAll('.dash-widget[data-loaded]').forEach(function(w) {
    w.dataset.loaded = 'false';
    w.dataset.collapsed = 'true';
    var body = w.querySelector('.dash-widget-body');
    if (body) { body.style.display = 'none'; body.innerHTML = ''; }
    var chevron = w.querySelector('.dash-widget-chevron');
    if (chevron) chevron.classList.remove('open');
  });

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

    // П.1: Чипы с цветом загрузки
    renderMonthChips(data.available_years || [currentYear], data.months || []);
    renderHeroSub(data);

    // П.5 + П.9: KPI с sparklines и дельтой
    renderKPI(data.kpi, data.months || [], data.prev_kpi || null);

    // П.6: «Мои задачи» для руководителя
    if (isLeader && data.my_kpi) {
      renderMyKPI(data.my_kpi);
    } else {
      var myW = document.querySelector('.dash-widget[data-widget="mykpi"]');
      if (myW) myW.style.display = 'none';
    }

    renderTeam(data.team);

    // Свёрнутые виджеты
    var kpi = data.kpi;
    _updateCollapsedHeader('tasks', 'fas fa-tasks', 'Задачи — ' + MONTHS_FULL[currentMonth], kpi.done_count + kpi.inwork_count, 'var(--accent)');
    _updateCollapsedHeader('debts', 'fas fa-exclamation-triangle', 'Долги', kpi.total_debts, 'var(--danger)');
    _updateCollapsedHeader('done_late', 'fas fa-clock', 'Выполнены с просрочкой', kpi.done_late_count, '#d97706');
    _toggleWidgetByCount('debts', kpi.total_debts);
    _toggleWidgetByCount('done_late', kpi.done_late_count);

    if (!isLeader) {
      document.querySelectorAll('.dash-widget[data-widget="tasks"],.dash-widget[data-widget="debts"],.dash-widget[data-widget="donelate"]').forEach(function(w) {
        w.dataset.scopeType = 'personal';
      });
    }

    // Виджет «Ближайшие дедлайны»
    renderDeadlines(data.upcoming_deadlines || []);

    // П.8: Auto-sync уведомлений
    fetch('/api/notifications/sync/', {method: 'POST', headers: {'X-CSRFToken': getCSRFToken()}}).catch(function(){});
  })
  .catch(function(e) {
    console.error('Dashboard error:', e);
    document.getElementById('dashKPI').innerHTML =
      emptyStateHtml({icon:'fas fa-exclamation-triangle', title:'Ошибка загрузки', desc:'Попробуйте обновить страницу'});
  });
}

/* ── Виджет «Ближайшие дедлайны» ─────────────────────────────── */
function renderDeadlines(items) {
  var el = document.getElementById('dashDeadlines');
  if (!el) return;
  if (!items || items.length === 0) {
    el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--muted);">' +
      '<i class="fas fa-check-circle" style="font-size:24px;color:var(--success);margin-bottom:8px;display:block;"></i>' +
      'Нет дедлайнов в ближайшие 7 дней</div>';
    return;
  }
  var html = '<div class="dash-deadlines">';
  items.forEach(function(t) {
    var urgency = t.days_left <= 1 ? 'urgent' : (t.days_left <= 3 ? 'soon' : 'normal');
    var daysText = t.days_left === 0 ? 'сегодня' : (t.days_left === 1 ? 'завтра' : t.days_left + ' дн.');
    var dateFormatted = t.date_end ? new Date(t.date_end).toLocaleDateString('ru-RU', {day:'numeric', month:'short'}) : '';
    html += '<a class="dash-deadline-item ' + urgency + '" href="/works/plan/" title="Открыть в плане">' +
      '<div class="dash-deadline-days"><span class="dash-deadline-num">' + (t.days_left <= 0 ? '!' : t.days_left) + '</span>' +
      '<span class="dash-deadline-label">' + daysText + '</span></div>' +
      '<div class="dash-deadline-info">' +
      '<div class="dash-deadline-name">' + esc(t.work_name || 'Работа #' + t.id) + '</div>' +
      '<div class="dash-deadline-meta">' + esc(t.executor || '—') +
      (t.project ? ' · ' + esc(t.project) : '') +
      ' · ' + dateFormatted + '</div>' +
      '</div>' +
      '</a>';
  });
  html += '</div>';
  el.innerHTML = html;
}

/* ── CSRF token ─────────────────────────────────────────────────── */
function getCSRFToken() {
  var c = document.cookie.match(/csrftoken=([^;]+)/);
  return c ? c[1] : '';
}

/* ── Заголовки свёрнутых виджетов ─────────────────────────────── */
function _updateCollapsedHeader(widgetName, iconCls, label, count, iconColor) {
  var wMap = {tasks: 'tasks', debts: 'debts', done_late: 'donelate'};
  var widget = document.querySelector('.dash-widget[data-widget="' + (wMap[widgetName] || widgetName) + '"]');
  if (!widget) return;
  var span = widget.querySelector('.dash-widget-header > span');
  if (span) {
    var chevron = '<i class="fas fa-chevron-right dash-widget-chevron"></i>';
    var exportBtn = '';
    // П.7: Кнопка экспорта для debts и done_late
    if (widgetName === 'debts' || widgetName === 'done_late') {
      var expType = widgetName === 'done_late' ? 'done_late' : 'debts';
      exportBtn = ' <a href="/api/dashboard/export/?year=' + currentYear + '&month=' + currentMonth +
        '&type=' + expType + '" class="dash-export-btn" title="Скачать CSV" onclick="event.stopPropagation();">' +
        '<i class="fas fa-download"></i></a>';
    }
    span.innerHTML = chevron + '<i class="' + iconCls + '" style="color:' + iconColor + ';margin-right:6px;"></i>' +
      label + (count > 0 ? ' <span class="an-load-badge" style="font-size:11px;">' + count + '</span>' : '') + exportBtn;
  }
}

function _toggleWidgetByCount(widgetName, count) {
  var wMap = {tasks: 'tasks', debts: 'debts', done_late: 'donelate'};
  var widget = document.querySelector('.dash-widget[data-widget="' + (wMap[widgetName] || widgetName) + '"]');
  if (!widget) return;
  widget.style.display = count === 0 ? 'none' : '';
}

/* ── Раскрытие/сворачивание виджета ───────────────────────────── */
window.dashToggleWidget = function(headerEl) {
  var widget = headerEl.closest('.dash-widget');
  if (!widget) return;
  var body = widget.querySelector('.dash-widget-body');
  if (!body) return;
  var isCollapsed = widget.dataset.collapsed === 'true';
  if (isCollapsed) {
    widget.dataset.collapsed = 'false';
    body.style.display = '';
    var chevron = widget.querySelector('.dash-widget-chevron');
    if (chevron) chevron.classList.add('open');
    if (widget.dataset.loaded === 'false') {
      widget.dataset.loaded = 'loading';
      body.innerHTML = '<div style="padding:12px;color:var(--muted);"><i class="fas fa-spinner fa-spin"></i> Загрузка...</div>';
      _fetchWidgetData(widget);
    }
  } else {
    widget.dataset.collapsed = 'true';
    body.style.display = 'none';
    var chevron2 = widget.querySelector('.dash-widget-chevron');
    if (chevron2) chevron2.classList.remove('open');
  }
};

function _fetchWidgetData(widget) {
  var wName = widget.dataset.widget;
  var body = widget.querySelector('.dash-widget-body');
  var isPersonal = widget.dataset.scopeType === 'personal';

  if (isPersonal && lastData && lastData.employee) {
    var empId = lastData.employee.id;
    fetch('/api/dashboard/employee/' + empId + '/?year=' + currentYear + '&month=' + currentMonth)
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(data) {
      widget.dataset.loaded = 'true';
      if (wName === 'tasks') renderTasks(data.tasks || [], false);
      else if (wName === 'debts') renderDebts(data.debts || [], false);
    })
    .catch(function() {
      widget.dataset.loaded = 'false';
      body.innerHTML = '<div style="padding:12px;color:var(--danger);">Ошибка загрузки</div>';
    });
    return;
  }

  var typeMap = {tasks: 'tasks', debts: 'debts', donelate: 'done_late'};
  var scopeType = typeMap[wName] || wName;

  fetch('/api/dashboard/scope/?year=' + currentYear + '&month=' + currentMonth + '&type=' + scopeType)
  .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(function(data) {
    widget.dataset.loaded = 'true';
    var items = data.items || [];
    if (wName === 'tasks') renderTasks(items, true);
    else if (wName === 'debts') renderDebts(items, true);
    else if (wName === 'donelate') renderDoneLate(items, true);
  })
  .catch(function() {
    widget.dataset.loaded = 'false';
    body.innerHTML = '<div style="padding:12px;color:var(--danger);">Ошибка загрузки</div>';
  });
}

/* ── Навигация ──────────────────────────────────────────────────── */
window.dashSetYear = function(y) { currentYear = y; loadDashboard(); };
window.dashSetMonth = function(m) { currentMonth = m; loadDashboard(); };

/* ── П.1: Чипы месяцев с цветным индикатором загрузки ────────── */
function renderMonthChips(years, months) {
  var monthMap = {};
  (months || []).forEach(function(m) { monthMap[m.month] = m; });

  var html = '<div class="an-toolbar-panel">';
  if (years && years.length > 1) {
    html += '<div class="dash-year-nav">';
    var idx = years.indexOf(currentYear);
    html += '<button' + (idx > 0 ? ' onclick="dashSetYear(' + years[idx-1] + ')"' : ' disabled style="opacity:0.3;cursor:default;"') + '><i class="fas fa-chevron-left"></i></button>';
    html += '<span class="dash-year-label">' + currentYear + '</span>';
    html += '<button' + (idx < years.length - 1 ? ' onclick="dashSetYear(' + years[idx+1] + ')"' : ' disabled style="opacity:0.3;cursor:default;"') + '><i class="fas fa-chevron-right"></i></button>';
    html += '</div>';
  } else {
    html += '<span class="dash-year-label" style="margin-right:12px;">' + currentYear + '</span>';
  }
  html += '<div class="an-chips">';
  for (var m = 1; m <= 12; m++) {
    var cls = m === currentMonth ? 'an-chip active' : 'an-chip';
    var mData = monthMap[m];
    var dotCls = '';
    if (mData && mData.load_pct > 0) {
      dotCls = mData.load_pct > 100 ? 'chip-dot-over' : (mData.load_pct >= 80 ? 'chip-dot-warn' : 'chip-dot-ok');
    }
    html += '<button class="' + cls + '" onclick="dashSetMonth(' + m + ')">';
    html += MONTHS_SHORT[m];
    if (dotCls) html += '<span class="chip-dot ' + dotCls + '"></span>';
    html += '</button>';
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
    parts.push('<span style="background:rgba(239,68,68,0.25);padding:2px 10px;border-radius:8px;font-weight:600;"><i class="fas fa-exclamation-circle"></i> Долги: ' + kpi.total_debts + '</span>');
  }
  if (kpi.inwork_count > 0) {
    parts.push('<span style="background:rgba(245,158,11,0.25);padding:2px 10px;border-radius:8px;font-weight:600;"><i class="fas fa-clock"></i> В работе: ' + kpi.inwork_count + '</span>');
  }
  if (kpi.total_debts === 0 && kpi.inwork_count === 0) {
    parts.push('<span style="opacity:0.75;">Все задачи в порядке <i class="fas fa-check-circle"></i></span>');
  }
  el.innerHTML = MONTHS_FULL[currentMonth] + ' ' + currentYear + ' &nbsp; ' + parts.join(' ');
}

/* ── П.5: Sparkline (мини-график за 12 месяцев) ─────────────────── */
function _sparklineHtml(months, field, w, h) {
  if (!months || months.length < 2) return '';
  var vals = months.map(function(m) { return m[field] || 0; });
  var max = Math.max.apply(null, vals) || 1;
  var points = [];
  var step = w / (vals.length - 1);
  for (var i = 0; i < vals.length; i++) {
    points.push(Math.round(step * i) + ',' + Math.round(h - (vals[i] / max) * h));
  }
  // Текущий месяц — выделенная точка
  var cx = Math.round(step * (currentMonth - 1));
  var cy = Math.round(h - (vals[currentMonth - 1] / max) * h);
  return '<svg class="dash-sparkline" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
    '<polyline points="' + points.join(' ') + '" fill="none" stroke="var(--accent)" stroke-width="1.5" />' +
    '<circle cx="' + cx + '" cy="' + cy + '" r="2.5" fill="var(--accent)" />' +
    '</svg>';
}

/* ── П.9: Дельта — отключена (визуально загромождала карточки) ─── */
function _deltaHtml() { return ''; }

/* ── П.2 + П.5 + П.9: KPI-карточки (кликабельные, sparkline, дельта) */
function renderKPI(kpi, months, prevKpi) {
  var loadCls = loadBadgeCls(kpi.load_pct);
  var colorMap = {ok: 'an-val-green', warn: 'an-val-yellow', over: 'an-val-red'};
  var pv = prevKpi || {};

  var cards = [
    { val: fmtPct(kpi.load_pct), label: 'Загрузка', cls: colorMap[loadCls] || '' },
    { val: fmtHrs(kpi.planned_hours) + ' / ' + fmtHrs(kpi.norm_hours), label: 'План / Норма (ч)', cls: 'an-val-accent' },
    { val: kpi.done_count, label: 'Выполнено', cls: 'an-val-green', extra: _deltaHtml(kpi.done_count, pv.done_count, false) },
    { val: kpi.inwork_count, label: 'В работе', cls: 'an-val-accent', action: 'tasks' },
    { val: kpi.total_debts, label: 'Долги', cls: kpi.total_debts > 0 ? 'an-val-red' : 'an-val-green', action: 'debts', extra: _deltaHtml(kpi.total_debts, pv.total_debts, true) },
  ];

  if (kpi.on_time_pct >= 0 && (kpi.total_done || 0) >= 3) {
    cards.push({ val: fmtPct(kpi.on_time_pct), label: '% в срок', cls: kpi.on_time_pct >= 90 ? 'an-val-green' : (kpi.on_time_pct >= 70 ? 'an-val-yellow' : 'an-val-red'), extra: _deltaHtml(kpi.on_time_pct, pv.on_time_pct, false) });
  }
  if (kpi.avg_overdue_days > 0 && kpi.total_debts > 0) {
    cards.push({ val: kpi.avg_overdue_days + ' дн.', label: 'Ср. просрочка', cls: 'an-val-red' });
  }

  var html = '';
  cards.forEach(function(c) {
    // П.2: кликабельные карточки
    var clickAttr = c.action ? ' onclick="dashOpenWidget(\'' + c.action + '\')" style="cursor:pointer;"' : '';
    html += '<div class="an-summary-card"' + clickAttr + '>';
    html += '<div class="an-summary-val ' + c.cls + '">' + c.val + '</div>';
    html += '<div class="an-summary-label">' + c.label + '</div>';
    if (c.extra) html += '<div class="an-summary-extra">' + c.extra + '</div>';
    html += '</div>';
  });
  document.getElementById('dashKPI').innerHTML = html;
}

/* П.2: Клик по KPI → раскрытие соответствующего виджета */
window.dashOpenWidget = function(widgetName) {
  var wMap = {tasks: 'tasks', debts: 'debts', done_late: 'donelate'};
  var widget = document.querySelector('.dash-widget[data-widget="' + (wMap[widgetName] || widgetName) + '"]');
  if (!widget) return;
  if (widget.style.display === 'none') return; // скрыт (count=0)
  if (widget.dataset.collapsed === 'true') {
    var header = widget.querySelector('.dash-widget-header');
    if (header) header.click();
  }
  widget.scrollIntoView({behavior: 'smooth', block: 'start'});
};

/* ── П.6: «Мои задачи» для руководителя ─────────────────────────── */
function renderMyKPI(myKpi) {
  var widget = document.querySelector('.dash-widget[data-widget="mykpi"]');
  if (!widget) return;
  widget.style.display = '';
  var el = document.getElementById('dashMyKPI');
  if (!el) return;

  var cards = [
    { val: fmtPct(myKpi.load_pct), label: 'Моя загрузка', cls: 'an-val-accent' },
    { val: myKpi.done_count, label: 'Выполнено', cls: 'an-val-green' },
    { val: myKpi.inwork_count, label: 'В работе', cls: 'an-val-accent' },
    { val: myKpi.total_debts, label: 'Мои долги', cls: myKpi.total_debts > 0 ? 'an-val-red' : 'an-val-green' },
  ];

  var html = '';
  cards.forEach(function(c) {
    html += '<div class="an-summary-card an-summary-card-sm">';
    html += '<div class="an-summary-val ' + c.cls + '">' + c.val + '</div>';
    html += '<div class="an-summary-label">' + c.label + '</div>';
    html += '</div>';
  });
  el.innerHTML = html;
}

/* ── Команда: отделы → сектора → сотрудники ──────────────────────── */
function renderTeam(team) {
  var el = document.getElementById('dashTeam');
  var widget = el.closest('.dash-widget');
  if (!team || !team.departments || !team.departments.length) {
    el.innerHTML = '';
    if (widget) widget.style.display = 'none';
    return;
  }
  if (widget) { widget.style.display = ''; _updateWidgetHeader(widget, '<i class="fas fa-users" style="color:var(--accent);margin-right:6px;"></i>Команда (' + team.total_employees + ') &nbsp; <span class="an-load-badge ' + loadBadgeCls(team.avg_load_pct) + '">' + fmtPct(team.avg_load_pct) + ' ср.загрузка</span>' + (team.total_overdue > 0 ? ' &nbsp; <span class="an-load-badge over">' + team.total_overdue + ' просроч.</span>' : '')); }

  // П.4: Поиск по сотрудникам
  var html = '<div class="dash-team-search-wrap">';
  html += '<input type="text" class="dash-team-search" id="dashTeamSearch" placeholder="Поиск по ФИО..." oninput="dashFilterTeam(this.value)">';
  html += '</div>';

  // П.3: Отделы с просрочками показываем, остальные скрыты
  var deptWithOverdue = [];
  var deptWithout = [];
  team.departments.forEach(function(dept) {
    if (dept.overdue_count > 0) deptWithOverdue.push(dept);
    else deptWithout.push(dept);
  });

  // Рендерим отделы с просрочками
  deptWithOverdue.forEach(function(dept) {
    html += _renderDeptBlock(dept, false);
  });

  // Остальные отделы — в сворачиваемой секции
  if (deptWithout.length > 0) {
    html += '<div class="dash-more-depts">';
    html += '<button class="dash-show-all-btn" onclick="dashToggleAllDepts(this)"><i class="fas fa-chevron-down"></i> Показать ещё ' + deptWithout.length + ' отд. (без просрочек)</button>';
    html += '<div class="dash-more-depts-body" style="display:none;">';
    deptWithout.forEach(function(dept) {
      html += _renderDeptBlock(dept, false);
    });
    html += '</div></div>';
  }

  el.innerHTML = html;
}

function _renderDeptBlock(dept) {
  var html = '<div class="dash-dept" data-dept-code="' + esc(dept.code) + '">';
  html += '<div class="dash-dept-header" onclick="dashToggleDept(this)">';
  html += '<i class="fas fa-chevron-right dash-dept-toggle"></i>';
  html += '<strong>' + esc(dept.code) + '</strong>';
  if (dept.name) html += ' <span class="dash-dept-name">' + esc(dept.name) + '</span>';
  html += ' <span class="dash-dept-meta">' + dept.count + ' чел.';
  html += ' &middot; ' + fmtPct(dept.avg_load_pct) + ' загр.';
  if (dept.overdue_count > 0) {
    html += ' &middot; <span class="an-load-badge over" style="font-size:11px;">' + dept.overdue_count + ' просроч.</span>';
  }
  html += '</span></div>';
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
    html += '</span></div>';
    sector.employees.forEach(function(e) {
      html += _renderEmployeeDropdown(e);
    });
    html += '</div>';
  });

  html += '</div></div>';
  return html;
}

/* П.3: Показать все отделы */
window.dashToggleAllDepts = function(btn) {
  var body = btn.nextElementSibling;
  if (!body) return;
  var isHidden = body.style.display === 'none';
  body.style.display = isHidden ? '' : 'none';
  btn.innerHTML = isHidden
    ? '<i class="fas fa-chevron-up"></i> Скрыть отделы без просрочек'
    : '<i class="fas fa-chevron-down"></i> Показать ещё ' + body.querySelectorAll('.dash-dept').length + ' отд. (без просрочек)';
};

/* П.4: Фильтр команды по ФИО */
window.dashFilterTeam = function(query) {
  var q = query.toLowerCase().trim();
  document.querySelectorAll('.dash-emp').forEach(function(emp) {
    var name = emp.querySelector('.dash-emp-name');
    if (!name) return;
    emp.style.display = (!q || name.textContent.toLowerCase().indexOf(q) >= 0) ? '' : 'none';
  });
  // Скрыть пустые сектора/отделы
  document.querySelectorAll('.dash-sector').forEach(function(sector) {
    var visible = sector.querySelectorAll('.dash-emp:not([style*="display: none"])');
    sector.style.display = visible.length ? '' : 'none';
  });
  document.querySelectorAll('.dash-dept').forEach(function(dept) {
    var visible = dept.querySelectorAll('.dash-emp:not([style*="display: none"])');
    // Показываем если есть сотрудники или нет запроса
    if (q && !visible.length) {
      dept.style.display = 'none';
    } else {
      dept.style.display = '';
      // При поиске раскрываем body
      if (q && visible.length) {
        var body = dept.querySelector('.dash-dept-body');
        if (body) body.style.display = 'block';
        var toggle = dept.querySelector('.dash-dept-toggle');
        if (toggle) toggle.classList.add('open');
      }
    }
  });
  // Раскрыть «Показать ещё» при поиске
  if (q) {
    var moreDepts = document.querySelector('.dash-more-depts-body');
    if (moreDepts) moreDepts.style.display = '';
  }
};

/* ── Dropdown сотрудника ──────────────────────────────────────────── */
function _renderEmployeeDropdown(e) {
  var badgeCls = loadBadgeCls(e.load_pct);
  var hasContent = e.overdue_count > 0 || e.planned > 0;
  var html = '<div class="dash-emp">';
  html += '<div class="dash-emp-header' + (hasContent ? ' clickable' : '') + '"';
  if (hasContent) html += ' onclick="dashToggleEmp(this)" data-emp-id="' + e.id + '"';
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
  if (e.overdue_count > 0) html += '<span class="dash-emp-tag debt">' + e.overdue_count + ' долг.</span>';
  html += '</div>';
  if (hasContent) html += '<div class="dash-emp-body" style="display:none;" data-loaded="false"></div>';
  html += '</div>';
  return html;
}

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

/* ── Задачи / Долги / Done Late ─────────────────────────────────── */
function renderTasks(tasks, showExecutor) {
  var el = document.getElementById('dashTasks');
  var widget = el.closest('.dash-widget');
  if (widget) _updateWidgetHeader(widget, '<i class="fas fa-tasks" style="color:var(--accent);margin-right:6px;"></i>Задачи — ' + MONTHS_FULL[currentMonth] + (tasks && tasks.length ? ' (' + tasks.length + ')' : ''));
  if (!tasks || !tasks.length) {
    el.innerHTML = emptyStateHtml({icon:'fas fa-clipboard-check', title:'Нет задач на этот месяц', desc:'Все задачи выполнены или ещё не запланированы'});
    return;
  }
  el.innerHTML = _renderTasksTable(tasks, showExecutor);
}

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

function _renderTasksTable(tasks, showExecutor) {
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

/* ── Toggle helpers ─────────────────────────────────────────────── */
window.dashToggle = function(titleEl) {
  var body = titleEl.nextElementSibling;
  var toggle = titleEl.querySelector('.dash-toggle');
  if (body) body.classList.toggle('collapsed');
  if (toggle) toggle.classList.toggle('collapsed');
};

window.dashToggleDept = function(headerEl) {
  var body = headerEl.nextElementSibling;
  var toggle = headerEl.querySelector('.dash-dept-toggle');
  if (!body) return;
  var isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.classList.toggle('open', !isOpen);
};

window.dashToggleEmp = function(headerEl) {
  var body = headerEl.nextElementSibling;
  var toggle = headerEl.querySelector('.dash-emp-toggle');
  if (!body) return;
  var isOpen = body.style.display !== 'none';
  body.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.classList.toggle('open', !isOpen);

  if (!isOpen && body.dataset.loaded === 'false') {
    body.dataset.loaded = 'loading';
    var empId = headerEl.dataset.empId;
    body.innerHTML = '<div style="padding:8px;color:var(--muted);"><i class="fas fa-spinner fa-spin"></i> Загрузка...</div>';
    fetch('/api/dashboard/employee/' + empId + '/?year=' + currentYear + '&month=' + currentMonth)
    .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(data) {
      body.dataset.loaded = 'true';
      var html = '';
      if (data.tasks && data.tasks.length) {
        html += '<div class="dash-emp-label"><i class="fas fa-tasks"></i> ' + MONTHS_FULL[currentMonth] + '</div>';
        html += _renderCompactList(data.tasks);
      }
      if (data.debts && data.debts.length) {
        html += '<div class="dash-emp-label debt"><i class="fas fa-exclamation-triangle"></i> Долги</div>';
        html += _renderCompactList(data.debts);
      }
      if (!html) html = '<div style="padding:8px;color:var(--muted);">Нет задач</div>';
      body.innerHTML = html;
    })
    .catch(function() {
      body.dataset.loaded = 'false';
      body.innerHTML = '<div style="padding:8px;color:var(--danger);">Ошибка загрузки</div>';
    });
  }
};

/* ── Widget header ──────────────────────────────────────────────── */
function _updateWidgetHeader(widget, html) {
  var span = widget.querySelector('.dash-widget-header > span');
  if (span) span.innerHTML = html;
}

/* ── Widget customization & drag ─────────────────────────────────── */
var DASH_LAYOUT_KEY = 'dashboard_layout';
function getDashLayout() { try { return JSON.parse(localStorage.getItem(DASH_LAYOUT_KEY)); } catch(e) { return null; } }
function saveDashLayout(layout) { localStorage.setItem(DASH_LAYOUT_KEY, JSON.stringify(layout)); }

window.toggleDashCustomize = function() {
  var grid = document.getElementById('dashGrid');
  grid.classList.toggle('customize-mode');
  var btn = document.getElementById('dashCustomizeBtn');
  if (grid.classList.contains('customize-mode')) {
    btn.innerHTML = '<i class="fas fa-check"></i> Готово';
    btn.classList.add('btn-primary'); btn.classList.remove('btn-outline');
    document.querySelectorAll('.dash-widget').forEach(function(w) { w.setAttribute('draggable', 'true'); });
  } else {
    btn.innerHTML = '<i class="fas fa-th"></i> Настроить';
    btn.classList.remove('btn-primary'); btn.classList.add('btn-outline');
    document.querySelectorAll('.dash-widget').forEach(function(w) { w.removeAttribute('draggable'); });
    saveDashLayout(getCurrentLayout());
  }
};

window.toggleWidgetVisibility = function(btnEl) {
  var widget = btnEl.closest('.dash-widget');
  if (!widget) return;
  widget.classList.toggle('widget-hidden');
  var icon = btnEl.querySelector('i');
  icon.className = widget.classList.contains('widget-hidden') ? 'fas fa-eye-slash' : 'fas fa-eye';
};

function getCurrentLayout() {
  return Array.from(document.querySelectorAll('.dash-widget')).map(function(w, i) {
    return { id: w.dataset.widget, visible: !w.classList.contains('widget-hidden'), order: i };
  });
}

function applyDashLayout(layout) {
  if (!layout || !layout.length) return;
  var grid = document.getElementById('dashGrid');
  if (!grid) return;
  var widgetMap = {};
  grid.querySelectorAll('.dash-widget').forEach(function(w) { widgetMap[w.dataset.widget] = w; });
  layout.sort(function(a, b) { return a.order - b.order; });
  layout.forEach(function(item) {
    var widget = widgetMap[item.id];
    if (!widget) return;
    grid.appendChild(widget);
    if (!item.visible) { widget.classList.add('widget-hidden'); var icon = widget.querySelector('.dash-widget-toggle i'); if (icon) icon.className = 'fas fa-eye-slash'; }
    else widget.classList.remove('widget-hidden');
  });
}

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
    requestAnimationFrame(function() { if (dragWidget) dragWidget.classList.add('dragging-widget'); });
  });
  grid.addEventListener('dragover', function(e) {
    if (!dragWidget) return;
    e.preventDefault(); e.dataTransfer.dropEffect = 'move';
    var target = e.target.closest('.dash-widget');
    if (!target || target === dragWidget) return;
    grid.querySelectorAll('.drag-over-widget').forEach(function(w) { w.classList.remove('drag-over-widget'); });
    target.classList.add('drag-over-widget');
    var rect = target.getBoundingClientRect();
    if (e.clientY < rect.top + rect.height / 2) grid.insertBefore(dragWidget, target);
    else { var next = target.nextElementSibling; if (next) grid.insertBefore(dragWidget, next); else grid.appendChild(dragWidget); }
  });
  grid.addEventListener('dragleave', function(e) { var t = e.target.closest('.dash-widget'); if (t) t.classList.remove('drag-over-widget'); });
  grid.addEventListener('drop', function(e) { e.preventDefault(); cleanupDrag(); });
  grid.addEventListener('dragend', function() { cleanupDrag(); });
  function cleanupDrag() {
    if (dragWidget) { dragWidget.classList.remove('dragging-widget'); dragWidget = null; }
    grid.querySelectorAll('.drag-over-widget').forEach(function(w) { w.classList.remove('drag-over-widget'); });
  }
}

/* ── Init ─────────────────────────────────────────────────────────── */
loadDashboard();
applyDashLayout(getDashLayout());
initWidgetDrag();

})();
