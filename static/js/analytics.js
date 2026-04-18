/// <reference path="types.js" />
/**
 * analytics.js — Единый модуль аналитики «Личный план».
 * Режимы: Графики / Таблицы (переключатель).
 * Все фильтры — мульти-выбор (toggle чипов). Drill-down через таблицы.
 */
(function () {
  'use strict';

  /* ── Конфигурация из шаблона ──────────────────────────────────────────── */
  /** @type {AnalyticsConfig} */
  var cfg = JSON.parse(document.getElementById('an-config').textContent);

  /* ── Режим отображения ────────────────────────────────────────────────── */
  /** @type {'charts'|'tables'} */
  var currentMode = 'charts';

  /* Все фильтры — объекты {key: true} для мульти-выбора */
  /** @type {Object<number, boolean>} */
  var currentYears = {};
  /** @type {Object<number, boolean>} */
  var currentMonths = {};
  /** @type {Object<number, boolean>} */
  var currentProjectIds = {};
  /** @type {Object<number, boolean>} */
  var currentProductIds = {};
  /** @type {Object<number, boolean>} */
  var currentCenterIds = {};
  /** @type {Object<string, boolean>} */
  var currentDeptCodes = {};
  /** @type {Object<number, boolean>} */
  var currentSectorIds = {};
  /** @type {Object<number, boolean>} */
  var currentExecutorIds = {};

  currentYears[cfg.currentYear] = true;

  // MONTHS_SHORT — в utils.js (1-based: MONTHS_SHORT[1] = "Янв")

  var lastData = null;
  var chartBar = null;
  var _exportData = [];

  /* ── Утилиты — esc/loadBadgeCls/fmtPct/fmtHrs в utils.js ─────────────── */
  function escAttr(s) {
    return esc(s).replace(/'/g, '&#39;').replace(/"/g, '&quot;');
  }
  function getCSSVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function idsToList(obj) {
    var arr = [];
    for (var k in obj) {
      if (obj[k]) arr.push(k);
    }
    return arr;
  }

  function toggle(obj, key) {
    if (obj[key]) delete obj[key];
    else obj[key] = true;
  }

  function hasAny(obj) {
    for (var k in obj) {
      if (obj[k]) return true;
    }
    return false;
  }

  /* ── Переключение режимов ─────────────────────────────────────────────── */
  window.anSetMode = function (mode) {
    currentMode = mode;
    updateModeTabs();
    // Разные API для аналитики и отчётов — перезагружаем данные
    loadData();
  };

  function updateModeTabs() {
    var tabs = document.querySelectorAll('#anModeTabs .an-mode-tab');
    tabs.forEach(function (tab) {
      if (tab.getAttribute('data-mode') === currentMode) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });
  }

  /* ── API ─────────────────────────────────────────────────────────────── */
  function buildUrl() {
    var u = currentMode === 'tables' ? '/api/analytics/reports/' : '/api/analytics/plan/';
    var params = [];

    var yrs = idsToList(currentYears);
    if (yrs.length) params.push('years=' + yrs.join(','));

    var mos = idsToList(currentMonths);
    if (mos.length) params.push('months=' + mos.join(','));

    var pids = idsToList(currentProjectIds);
    if (pids.length) params.push('project_ids=' + pids.join(','));

    var prids = idsToList(currentProductIds);
    if (prids.length) params.push('product_ids=' + prids.join(','));

    var cids = idsToList(currentCenterIds);
    if (cids.length) params.push('center_ids=' + cids.join(','));

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
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.error) {
          el.innerHTML =
            '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> ' +
            esc(data.error) +
            '</div>';
          return;
        }
        lastData = data;
        try {
          renderToolbar(data);
          renderBreadcrumb(data);
          renderContent(data);
          // Снимок месяца — общий блок с СП. Показываем только при
          // строго одном выбранном годе и месяце (иначе бессмыслен).
          loadMonthSnapshot();
        } catch (renderErr) {
          console.error('Analytics render error:', renderErr);
          el.innerHTML =
            '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i> Ошибка отображения данных</div>';
        }
      })
      .catch(function (e) {
        console.error('Analytics error:', e);
        el.innerHTML =
          '<div class="an-empty"><i class="fas fa-exclamation-triangle"></i>Ошибка загрузки данных</div>';
      });
  }

  /* ── Навигация (мульти-toggle для всех фильтров) ─────────────────────── */
  window.anToggleYear = function (y) {
    toggle(currentYears, y);
    if (!hasAny(currentYears)) currentYears[y] = true;
    loadData();
  };
  window.anClearYears = function () {
    currentYears = {};
    currentYears[cfg.currentYear] = true;
    loadData();
  };

  window.anToggleMonth = function (m) {
    toggle(currentMonths, m);
    loadData();
  };
  window.anClearMonths = function () {
    currentMonths = {};
    loadData();
  };

  window.anToggleProject = function (id) {
    toggle(currentProjectIds, id);
    _pruneProducts();
    loadData();
  };
  window.anClearProjects = function () {
    currentProjectIds = {};
    currentProductIds = {};
    loadData();
  };

  window.anToggleProduct = function (id) {
    toggle(currentProductIds, id);
    loadData();
  };
  window.anClearProducts = function () {
    currentProductIds = {};
    loadData();
  };

  window.anToggleCenter = function (id) {
    toggle(currentCenterIds, id);
    currentDeptCodes = {};
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };
  window.anClearCenters = function () {
    currentCenterIds = {};
    currentDeptCodes = {};
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };

  window.anToggleDept = function (code) {
    toggle(currentDeptCodes, code);
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };
  window.anClearDepts = function () {
    currentDeptCodes = {};
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };

  window.anToggleSector = function (id) {
    toggle(currentSectorIds, id);
    currentExecutorIds = {};
    loadData();
  };
  window.anClearSectors = function () {
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };

  window.anToggleExecutor = function (id) {
    toggle(currentExecutorIds, id);
    loadData();
  };
  window.anClearExecutors = function () {
    currentExecutorIds = {};
    loadData();
  };

  // Drill-down через таблицы (ставит единственный фильтр)
  window.anDrillCenter = function (id) {
    currentCenterIds = {};
    currentCenterIds[id] = true;
    currentDeptCodes = {};
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };
  window.anDrillDept = function (code) {
    currentDeptCodes = {};
    currentDeptCodes[code] = true;
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };
  window.anDrillSector = function (id) {
    currentSectorIds = {};
    currentSectorIds[id] = true;
    currentExecutorIds = {};
    loadData();
  };
  window.anDrillEmployee = function (id) {
    currentExecutorIds = {};
    currentExecutorIds[id] = true;
    loadData();
  };
  window.anGoHome = function () {
    currentCenterIds = {};
    currentDeptCodes = {};
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };
  window.anGoDept = function (code) {
    currentDeptCodes = {};
    if (code) currentDeptCodes[code] = true;
    currentSectorIds = {};
    currentExecutorIds = {};
    loadData();
  };

  function _pruneProducts() {
    var pids = idsToList(currentProjectIds);
    if (!pids.length) return;
    var allProducts = (lastData && lastData.nav_products) || [];
    var validIds = {};
    allProducts.forEach(function (p) {
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

    // ── Группа 1: Год + Месяц ──
    html += '<div class="an-toolbar-row-inline">';

    html +=
      '<div class="an-toolbar-panel"><span class="an-toolbar-label">Год:</span><div class="an-chips">';
    (data.years || []).forEach(function (y) {
      var cls = currentYears[y] ? 'an-chip active' : 'an-chip';
      html += '<button class="' + cls + '" onclick="anToggleYear(' + y + ')">' + y + '</button>';
    });
    var yearCount = idsToList(currentYears).length;
    if (yearCount > 1) {
      html += '<button class="an-chip-clear" onclick="anClearYears()">сбросить</button>';
    }
    html += '</div></div>';

    html +=
      '<div class="an-toolbar-panel"><span class="an-toolbar-label">Месяц:</span><div class="an-chips">';
    for (var m = 1; m <= 12; m++) {
      var cls = currentMonths[m] ? 'an-chip active' : 'an-chip';
      html +=
        '<button class="' +
        cls +
        '" onclick="anToggleMonth(' +
        m +
        ')">' +
        MONTHS_SHORT[m] +
        '</button>';
    }
    if (hasAny(currentMonths)) {
      html += '<button class="an-chip-clear" onclick="anClearMonths()">сбросить</button>';
    }
    html += '</div></div>';

    html += '</div>';

    // ── Группа 2: Проект + Изделие ──
    var projects = data.nav_projects || [];
    var allProducts = data.nav_products || [];
    var activeProjects = idsToList(currentProjectIds);
    var products =
      activeProjects.length > 0
        ? allProducts.filter(function (p) {
            return currentProjectIds[p.project_id];
          })
        : allProducts;
    if (projects.length > 0 || products.length > 0) {
      html += '<div class="an-toolbar-row-inline">';
      if (projects.length > 0) {
        html +=
          '<div class="an-toolbar-panel"><span class="an-toolbar-label">Проект:</span><div class="an-chips">';
        projects.forEach(function (p) {
          var cls = currentProjectIds[p.id] ? 'an-chip active' : 'an-chip';
          html +=
            '<button class="' +
            cls +
            '" onclick="anToggleProject(' +
            p.id +
            ')">' +
            esc(p.name) +
            '</button>';
        });
        if (hasAny(currentProjectIds)) {
          html += '<button class="an-chip-clear" onclick="anClearProjects()">сбросить</button>';
        }
        html += '</div></div>';
      }
      if (products.length > 0) {
        html +=
          '<div class="an-toolbar-panel"><span class="an-toolbar-label">Изделие:</span><div class="an-chips">';
        products.forEach(function (p) {
          var cls = currentProductIds[p.id] ? 'an-chip active' : 'an-chip';
          html +=
            '<button class="' +
            cls +
            '" onclick="anToggleProduct(' +
            p.id +
            ')">' +
            esc(p.name) +
            '</button>';
        });
        if (hasAny(currentProductIds)) {
          html += '<button class="an-chip-clear" onclick="anClearProducts()">сбросить</button>';
        }
        html += '</div></div>';
      }
      html += '</div>';
    }

    // ── Группа 3: Центр + Отдел ──
    var centers = data.nav_centers || [];
    var depts = data.nav_depts || [];
    var activeCenters = idsToList(currentCenterIds);
    if (activeCenters.length > 0) {
      var centerSet = {};
      activeCenters.forEach(function (cid) {
        centerSet[cid] = true;
      });
      depts = depts.filter(function (d) {
        return d.center_id && centerSet[d.center_id];
      });
    }
    if (centers.length > 0 || depts.length > 0) {
      html += '<div class="an-toolbar-row-inline">';
      if (centers.length > 0) {
        html +=
          '<div class="an-toolbar-panel"><span class="an-toolbar-label">Центр:</span><div class="an-chips">';
        centers.forEach(function (c) {
          var cls = currentCenterIds[c.id] ? 'an-chip active' : 'an-chip';
          html +=
            '<button class="' +
            cls +
            '" onclick="anToggleCenter(' +
            c.id +
            ')">' +
            esc(c.code) +
            '</button>';
        });
        if (hasAny(currentCenterIds)) {
          html += '<button class="an-chip-clear" onclick="anClearCenters()">сбросить</button>';
        }
        html += '</div></div>';
      }
      if (depts.length > 0) {
        html +=
          '<div class="an-toolbar-panel"><span class="an-toolbar-label">Отдел:</span><div class="an-chips">';
        depts.forEach(function (d) {
          var code = d.code || d;
          var cls = currentDeptCodes[code] ? 'an-chip active' : 'an-chip';
          html +=
            '<button class="' +
            cls +
            '" onclick="anToggleDept(\'' +
            escAttr(code) +
            '\')">' +
            esc(code) +
            '</button>';
        });
        if (hasAny(currentDeptCodes)) {
          html += '<button class="an-chip-clear" onclick="anClearDepts()">сбросить</button>';
        }
        html += '</div></div>';
      }
      html += '</div>';
    }

    // Секторы (мульти-выбор чипами)
    var sectors = data.nav_sectors || [];
    if (sectors.length > 0) {
      html +=
        '<div class="an-toolbar-panel"><span class="an-toolbar-label">Сектор:</span><div class="an-chips">';
      sectors.forEach(function (s) {
        var cls = currentSectorIds[s.id] ? 'an-chip active' : 'an-chip';
        html +=
          '<button class="' +
          cls +
          '" onclick="anToggleSector(' +
          s.id +
          ')">' +
          esc(s.name) +
          '</button>';
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
    var canGoHome =
      role === 'admin' ||
      role === 'ntc_head' ||
      role === 'ntc_deputy' ||
      role === 'chief_designer' ||
      role === 'deputy_gd_econ';

    if (data.view === 'centers') {
      parts.push(
        '<span style="font-weight:600;"><i class="fas fa-city" style="margin-right:4px;color:var(--accent);"></i>Все центры</span>',
      );
    } else if (data.view === 'all') {
      if (canGoHome) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-city"></i> Центры</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      if (data.center) {
        parts.push(
          '<span style="font-weight:600;"><i class="fas fa-building" style="margin-right:4px;color:var(--accent);"></i>' +
            esc(data.center.name || data.center.code) +
            ' — Отделы</span>',
        );
      } else {
        parts.push(
          '<span style="font-weight:600;"><i class="fas fa-building" style="margin-right:4px;color:var(--accent);"></i>Все отделы</span>',
        );
      }
    } else if (data.view === 'dept') {
      if (canGoHome) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-city"></i> Центры</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      parts.push(
        '<span style="font-weight:600;"><i class="fas fa-layer-group" style="margin-right:4px;color:var(--accent);"></i>Отдел ' +
          esc(data.dept ? data.dept.name || data.dept.code : '') +
          '</span>',
      );
    } else if (data.view === 'sector') {
      if (canGoHome) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-city"></i> Центры</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      var deptCodes = idsToList(currentDeptCodes);
      if (
        deptCodes.length ||
        (data.role_info && (role === 'dept_head' || role === 'dept_deputy'))
      ) {
        var deptCode = deptCodes[0] || data.role_info.dept;
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoDept(\'' +
            escAttr(deptCode) +
            '\')">' +
            esc(deptCode) +
            '</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      parts.push(
        '<span style="font-weight:600;"><i class="fas fa-users" style="margin-right:4px;color:var(--accent);"></i>Сектор ' +
          esc(data.sector ? data.sector.name : '') +
          '</span>',
      );
    } else if (data.view === 'employee') {
      if (canGoHome) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-city"></i> Центры</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      var empInfo = data.employee || {};
      if (empInfo.dept) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoDept(\'' +
            escAttr(empInfo.dept) +
            '\')">' +
            esc(empInfo.dept) +
            '</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      parts.push(
        '<span style="font-weight:600;"><i class="fas fa-user" style="margin-right:4px;color:var(--accent);"></i>' +
          esc(empInfo.name) +
          '</span>',
      );
    } else if (data.view === 'employees') {
      if (canGoHome) {
        parts.push(
          '<a class="an-breadcrumb-link" onclick="anGoHome()"><i class="fas fa-city"></i> Центры</a>',
        );
        parts.push('<span class="an-breadcrumb-sep">›</span>');
      }
      parts.push('<span style="font-weight:600;">Выбранные сотрудники</span>');
    }

    bc.innerHTML = parts.join(' ');
  }

  /* ── Контент — маршрутизация по режиму и view ─────────────────────────── */
  function renderContent(data) {
    var el = document.getElementById('anContent');

    // Очищаем экспорт — будет пересоздан в _setupExport
    var expTop = document.getElementById('anExportTop');
    if (expTop) expTop.innerHTML = '';

    if (currentMode === 'charts') {
      switch (data.view) {
        case 'centers':
          renderCentersCharts(el, data);
          break;
        case 'all':
          renderAllDeptsCharts(el, data);
          break;
        case 'dept':
          renderDeptCharts(el, data);
          break;
        case 'sector':
          renderSectorCharts(el, data);
          break;
        case 'employee':
          renderEmployeeCharts(el, data);
          break;
        case 'employees':
          renderSectorCharts(el, data);
          break;
        default:
          el.innerHTML = '<div class="an-empty"><i class="fas fa-chart-bar"></i>Нет данных</div>';
      }
    } else {
      switch (data.view) {
        case 'centers':
          renderCentersTables(el, data);
          break;
        case 'all':
          renderAllDeptsTables(el, data);
          break;
        case 'dept':
          renderDeptTables(el, data);
          break;
        case 'sector':
          renderSectorTables(el, data);
          break;
        case 'employee':
          renderEmployeeTables(el, data);
          break;
        case 'employees':
          renderSectorTables(el, data);
          break;
        default:
          el.innerHTML = '<div class="an-empty"><i class="fas fa-table"></i>Нет данных</div>';
      }
    }

    // Подключаем экспорт для обоих режимов
    _setupExport(data);
  }

  /* ═══════════════════════════════════════════════════════════════════════
   РЕЖИМ «ГРАФИКИ» — графики + таблицы drill-down
   ═══════════════════════════════════════════════════════════════════════ */

  /* ── Уровень центров (charts + tables) ────────────────────────────────── */

  function renderCentersCharts(el, data) {
    var centers = data.centers || [];
    if (!centers.length) {
      el.innerHTML =
        '<div class="an-empty"><i class="fas fa-sitemap"></i>Нет данных по центрам</div>';
      return;
    }

    var html = _renderCentersSummary(data, centers);

    html += '<div class="an-widgets">';
    html +=
      '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
    html += '</div>';

    html += '<div class="an-widget an-widget-full" style="padding:0;">';
    html +=
      '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-sitemap"></i> Центры</div>';
    html += '<div style="overflow-x:auto;padding:0 12px 10px;">';
    html += '<table class="an-list-table"><thead><tr>';
    html +=
      '<th>Центр</th><th>Название</th><th class="cell-num">Отделов</th><th class="cell-num">Сотрудников</th>';
    html +=
      '<th class="cell-num">План (ч)</th><th class="cell-num">Норма (ч)</th><th class="cell-num">Загрузка</th>';
    html += '</tr></thead><tbody>';

    centers.forEach(function (c) {
      var badgeCls = loadBadgeCls(c.total_load_pct);
      html += '<tr onclick="anDrillCenter(' + c.id + ')" style="cursor:pointer;">';
      html += '<td><strong>' + esc(c.code) + '</strong></td>';
      html += '<td>' + esc(c.name) + '</td>';
      html += '<td class="cell-num">' + (c.dept_count || 0) + '</td>';
      html += '<td class="cell-num">' + (c.employee_count || 0) + '</td>';
      html += '<td class="cell-num">' + fmtHrs(c.total_planned) + '</td>';
      html += '<td class="cell-num">' + fmtHrs(c.total_norm) + '</td>';
      html +=
        '<td class="cell-num"><span class="an-load-badge ' +
        badgeCls +
        '">' +
        fmtPct(c.total_load_pct) +
        '</span></td>';
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';
    el.innerHTML = html;
    renderBarChart(data.months || []);
  }

  /* ── Общие хелперы отчётов ──────────────────────────────────────────── */

  function _rptStatusBadge(status, days) {
    var map = {
      done: '<span class="rpt-status done">✓ Выполнено</span>',
      inwork: '<span class="rpt-status inwork">В работе</span>',
      overdue:
        '<span class="rpt-status overdue">Просрочено' +
        (days ? ' · ' + days + ' дн.' : '') +
        '</span>',
      debt: '<span class="rpt-status debt">Долг' + (days ? ' · ' + days + ' дн.' : '') + '</span>',
    };
    return map[status] || '';
  }

  function _rptCompletionBar(pct) {
    var cls = pct >= 50 ? 'green' : pct >= 10 ? 'yellow' : 'red';
    var colorCls = pct >= 50 ? '' : pct >= 10 ? '' : ' style="color:var(--danger)"';
    return (
      '<div class="cell-bar">' +
      '<div class="cell-bar-track"><div class="cell-bar-fill ' +
      cls +
      '" style="width:' +
      Math.min(pct, 100) +
      '%"></div></div>' +
      '<div class="cell-bar-pct"' +
      colorCls +
      '>' +
      fmtPct(pct) +
      '</div></div>'
    );
  }

  function _rptSummaryCards(data) {
    var html = '<div class="rpt-summary-header">';
    html += '<div class="an-summary">';
    html +=
      '<div class="an-summary-card an-summary-accent"><div class="an-summary-val an-val-accent">' +
      fmtNum(data.total || 0) +
      '</div><div class="an-summary-label">Всего задач</div></div>';
    var doneSub = fmtPct(data.completion_pct || 0);
    if ((data.done_intime || 0) + (data.done_early || 0) > 0) {
      doneSub +=
        ' &middot; в срок ' +
        fmtNum(data.done_intime || 0) +
        ' + опереж. ' +
        fmtNum(data.done_early || 0);
    }
    html +=
      '<div class="an-summary-card an-summary-success"><div class="an-summary-val an-val-green">' +
      fmtNum(data.done || 0) +
      '</div><div class="an-summary-label">Выполнено</div><div class="an-summary-sub">' +
      doneSub +
      '</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val">' +
      fmtNum(data.inwork || 0) +
      '</div><div class="an-summary-label">В работе</div></div>';
    html +=
      '<div class="an-summary-card an-summary-danger"><div class="an-summary-val an-val-red">' +
      fmtNum(data.overdue || 0) +
      '</div><div class="an-summary-label">Просрочено</div></div>';
    var debtSub = 'из прошлых мес.';
    if ((data.debts_closed || 0) + (data.debts_hanging || 0) > 0) {
      debtSub =
        'закрыто ' +
        fmtNum(data.debts_closed || 0) +
        ' + висит ' +
        fmtNum(data.debts_hanging || 0);
    }
    html +=
      '<div class="an-summary-card an-summary-warn"><div class="an-summary-val an-val-yellow">' +
      fmtNum(data.debts_total || 0) +
      '</div><div class="an-summary-label">Долги</div><div class="an-summary-sub">' +
      debtSub +
      '</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val">' +
      fmtHrs(data.plan_hours || 0) +
      (data.norm_hours ? ' / ' + fmtHrs(data.norm_hours) : '') +
      '</div><div class="an-summary-label">' +
      (data.norm_hours ? 'План / Норма (ч)' : 'План (часы)') +
      '</div></div>';
    html += '</div>';

    // Прогресс-бар
    var t = data.total || 1;
    var doneW = ((data.done || 0) / t) * 100;
    var overdueW = ((data.overdue || 0) / t) * 100;
    var inworkW = ((data.inwork || 0) / t) * 100;
    html += '<div class="rpt-progress">';
    html +=
      '<div class="rpt-progress-labels"><span>Прогресс выполнения</span><span>' +
      fmtNum(data.done || 0) +
      ' / ' +
      fmtNum(data.total || 0) +
      '</span></div>';
    html += '<div class="rpt-progress-bar">';
    html += '<div class="rpt-progress-done" style="width:' + doneW + '%"></div>';
    html += '<div class="rpt-progress-overdue" style="width:' + overdueW + '%"></div>';
    html += '<div class="rpt-progress-inwork" style="width:' + inworkW + '%"></div>';
    html += '</div>';
    html += '<div class="rpt-progress-legend">';
    html += '<span class="rpt-lg-done">Выполнено (' + fmtNum(data.done || 0) + ')</span>';
    html += '<span class="rpt-lg-overdue">Просрочено (' + fmtNum(data.overdue || 0) + ')</span>';
    html += '<span class="rpt-lg-inwork">В работе (' + fmtNum(data.inwork || 0) + ')</span>';
    html += '</div></div>';
    html += '</div>';
    return html;
  }

  function _rptDebtsBlock(data) {
    if (!data.debts_total) return '';
    var html = '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-exclamation-triangle"></i> Долги из прошлых периодов <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge-danger">' + fmtNum(data.debts_total) + ' задач</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';

    html += '<div class="rpt-debt-cards">';
    html +=
      '<div class="rpt-debt-card mild"><div class="rpt-debt-val">' +
      fmtNum(data.debts_1m || 0) +
      '</div><div class="rpt-debt-label">1 месяц</div></div>';
    html +=
      '<div class="rpt-debt-card medium"><div class="rpt-debt-val">' +
      fmtNum(data.debts_2_3m || 0) +
      '</div><div class="rpt-debt-label">2–3 месяца</div></div>';
    html +=
      '<div class="rpt-debt-card severe"><div class="rpt-debt-val">' +
      fmtNum(data.debts_3plus || 0) +
      '</div><div class="rpt-debt-label">3+ месяцев</div></div>';
    html += '</div>';

    // Группировка по подразделениям (центры/отделы/секторы)
    var units = data.debts_by_units || [];
    if (units.length > 0) {
      var groupLabels = { center: 'Центр', dept: 'Отдел', sector: 'Сектор' };
      var groupLabel = groupLabels[data.debts_group] || 'Подразделение';
      html += '<table class="rpt-tbl">';
      html += '<thead><tr><th>' + groupLabel + '</th>';
      html += '<th class="num">Всего</th><th class="num">1 мес</th>';
      html += '<th class="num">2–3 мес</th><th class="num">3+ мес</th></tr></thead>';
      html += '<tbody>';
      var totals = { total: 0, m1: 0, m23: 0, m3p: 0 };
      var drillGroup = data.debts_group;
      units.forEach(function (u) {
        totals.total += u.debts_total;
        totals.m1 += u.debts_1m;
        totals.m23 += u.debts_2_3m;
        totals.m3p += u.debts_3plus;
        var drillAttr = '';
        if (drillGroup === 'center') {
          drillAttr = ' onclick="anDrillCenter(' + u.id + ')" class="rpt-clickable"';
        } else if (drillGroup === 'dept') {
          drillAttr = ' onclick="anDrillDept(\'' + escAttr(u.id) + '\')" class="rpt-clickable"';
        } else if (drillGroup === 'sector') {
          drillAttr = ' onclick="anDrillSector(' + u.id + ')" class="rpt-clickable"';
        }
        html += '<tr' + drillAttr + '>';
        html += '<td class="bold">' + esc(u.name) + '</td>';
        html += '<td class="num" style="color:var(--danger)">' + fmtNum(u.debts_total) + '</td>';
        html += '<td class="num">' + fmtNum(u.debts_1m) + '</td>';
        html += '<td class="num">' + fmtNum(u.debts_2_3m) + '</td>';
        html += '<td class="num">' + fmtNum(u.debts_3plus) + '</td>';
        html += '</tr>';
      });
      html += '<tr class="rpt-total-row">';
      html += '<td class="bold">Итого</td>';
      html += '<td class="num bold" style="color:var(--danger)">' + fmtNum(totals.total) + '</td>';
      html += '<td class="num bold">' + fmtNum(totals.m1) + '</td>';
      html += '<td class="num bold">' + fmtNum(totals.m23) + '</td>';
      html += '<td class="num bold">' + fmtNum(totals.m3p) + '</td>';
      html += '</tr>';
      html += '</tbody></table>';
    }

    // Список задач-долгов (для уровня сектора/сотрудника, или детализация отдела)
    var debts = data.debt_tasks || [];
    if (debts.length > 0 && units.length > 0) {
      // Если есть и группировка, и задачи — сворачиваемый блок
      html += '<div class="rpt-subsection collapsed">';
      html +=
        '<div class="rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')" style="margin:12px 0 8px;font-size:0.9em">';
      html +=
        '<i class="fas fa-list"></i> Все задачи (' + (data.debt_tasks_total || debts.length) + ')';
      html += ' <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
      html += '<div class="rpt-section-body">';
    }
    if (debts.length > 0) {
      html += '<table class="rpt-tbl">';
      html += '<thead><tr><th>Задача</th><th>Проект</th><th>Исполнитель</th><th>Отдел</th>';
      html +=
        '<th class="num">Плановый срок</th><th class="num">Просрочка</th><th>Глубина</th></tr></thead>';
      html += '<tbody>';
      debts.forEach(function (d) {
        var depthCls = d.depth === '3plus' ? 'debt' : d.depth === '2_3m' ? 'debt' : 'overdue';
        var depthLabel = d.depth === '3plus' ? '3+ мес' : d.depth === '2_3m' ? '2–3 мес' : '1 мес';
        html += '<tr>';
        html += '<td class="bold">' + esc(d.work_name) + '</td>';
        html += '<td>' + esc(d.project_name) + '</td>';
        html += '<td>' + esc(d.executor) + '</td>';
        html += '<td class="muted">' + esc(d.dept) + '</td>';
        html += '<td class="num">' + fmtDate(d.date_end) + '</td>';
        html += '<td class="num" style="color:var(--danger)">' + d.days_overdue + ' дн.</td>';
        html += '<td><span class="rpt-status ' + depthCls + '">' + depthLabel + '</span></td>';
        html += '</tr>';
      });
      if (data.debt_tasks_total > debts.length) {
        html +=
          '<tr><td colspan="7" class="rpt-more">... ещё ' +
          (data.debt_tasks_total - debts.length) +
          ' задач</td></tr>';
      }
      html += '</tbody></table>';
      if (units.length > 0) {
        html += '</div></div>'; // rpt-section-body + rpt-subsection
      }
    }
    html += '</div>'; // rpt-section-body
    html += '</div>'; // rpt-section
    return html;
  }

  function _rptProjectsBlock(data) {
    var projects = data.projects || [];
    if (!projects.length) return '';
    var html = '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-folder"></i> По проектам <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge">' + projects.length + ' проектов</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';
    html += '<table class="rpt-tbl">';
    html += '<thead><tr><th>Проект</th><th class="num">Задач</th><th class="num">Выполнено</th>';
    html += '<th class="num">Просрочено</th><th class="num">Долги</th>';
    html += '<th class="num">План (ч)</th><th style="min-width:140px">Выполнение</th></tr></thead>';
    html += '<tbody>';
    var totals = { total: 0, done: 0, overdue: 0, debts: 0, hours: 0 };
    projects.forEach(function (p) {
      totals.total += p.total;
      totals.done += p.done;
      totals.overdue += p.overdue;
      totals.debts += p.debts_total;
      totals.hours += p.plan_hours;
      var pct = p.completion_pct || 0;
      html += '<tr>';
      html += '<td class="bold">' + esc(p.name) + '</td>';
      html += '<td class="num">' + fmtNum(p.total) + '</td>';
      html += '<td class="num" style="color:var(--success)">' + fmtNum(p.done) + '</td>';
      html += '<td class="num" style="color:var(--danger)">' + fmtNum(p.overdue) + '</td>';
      html += '<td class="num" style="color:#b91c1c">' + fmtNum(p.debts_total) + '</td>';
      html += '<td class="num">' + fmtHrs(p.plan_hours) + '</td>';
      html += '<td>' + _rptCompletionBar(pct) + '</td>';
      html += '</tr>';
    });
    // Итого
    var totalPct = totals.total > 0 ? (totals.done / totals.total) * 100 : 0;
    html += '<tr class="rpt-total-row">';
    html += '<td class="bold">Итого</td>';
    html += '<td class="num bold">' + fmtNum(totals.total) + '</td>';
    html += '<td class="num bold" style="color:var(--success)">' + fmtNum(totals.done) + '</td>';
    html += '<td class="num bold" style="color:var(--danger)">' + fmtNum(totals.overdue) + '</td>';
    html += '<td class="num bold" style="color:#b91c1c">' + fmtNum(totals.debts) + '</td>';
    html += '<td class="num bold">' + fmtHrs(totals.hours) + '</td>';
    html += '<td>' + _rptCompletionBar(totalPct) + '</td>';
    html += '</tr></tbody></table>';
    html += '</div>'; // rpt-section-body
    html += '</div>'; // rpt-section
    return html;
  }

  function _rptUnitTable(items, icon, nameKey, drillFn) {
    if (!items.length) return '';
    var html = '<table class="rpt-tbl">';
    html +=
      '<thead><tr><th>' +
      icon +
      '</th><th class="num">Сотр.</th><th class="num">Задач</th><th class="num">Выполнено</th>';
    html += '<th class="num">Просрочено</th><th class="num">Долги</th>';
    html +=
      '<th class="num">План (ч)</th><th class="num">Норма (ч)</th><th style="min-width:140px">Выполнение</th></tr></thead>';
    html += '<tbody>';
    var totals = { emps: 0, total: 0, done: 0, overdue: 0, debts: 0, hours: 0, norm: 0 };
    items.forEach(function (item) {
      var name = item[nameKey] || item.code || item.name || '';
      var pct = item.completion_pct || 0;
      var onclick = drillFn ? ' onclick="' + drillFn(item) + '" class="rpt-clickable"' : '';
      totals.emps += item.employee_count || 0;
      totals.total += item.total || 0;
      totals.done += item.done || 0;
      totals.overdue += item.overdue || 0;
      totals.debts += item.debts_total || 0;
      totals.hours += item.plan_hours || 0;
      totals.norm += item.norm_hours || 0;
      html += '<tr' + onclick + '>';
      html += '<td class="bold">' + esc(name) + '</td>';
      html += '<td class="num">' + fmtNum(item.employee_count || 0) + '</td>';
      html += '<td class="num">' + fmtNum(item.total) + '</td>';
      html += '<td class="num" style="color:var(--success)">' + fmtNum(item.done) + '</td>';
      html += '<td class="num" style="color:var(--danger)">' + fmtNum(item.overdue) + '</td>';
      html += '<td class="num" style="color:#b91c1c">' + fmtNum(item.debts_total) + '</td>';
      html += '<td class="num">' + fmtHrs(item.plan_hours) + '</td>';
      html += '<td class="num">' + fmtHrs(item.norm_hours) + '</td>';
      html += '<td>' + _rptCompletionBar(pct) + '</td>';
      html += '</tr>';
    });
    var totalPct = totals.total > 0 ? Math.round((totals.done / totals.total) * 1000) / 10 : 0;
    html += '<tr class="rpt-total-row">';
    html += '<td class="bold">Итого</td>';
    html += '<td class="num bold">' + fmtNum(totals.emps) + '</td>';
    html += '<td class="num bold">' + fmtNum(totals.total) + '</td>';
    html += '<td class="num bold" style="color:var(--success)">' + fmtNum(totals.done) + '</td>';
    html += '<td class="num bold" style="color:var(--danger)">' + fmtNum(totals.overdue) + '</td>';
    html += '<td class="num bold" style="color:#b91c1c">' + fmtNum(totals.debts) + '</td>';
    html += '<td class="num bold">' + fmtHrs(totals.hours) + '</td>';
    html += '<td class="num bold">' + fmtHrs(totals.norm) + '</td>';
    html += '<td>' + _rptCompletionBar(totalPct) + '</td>';
    html += '</tr>';
    html += '</tbody></table>';
    return html;
  }

  function fmtNum(n) {
    if (n === null || n === undefined) return '0';
    return n.toLocaleString('ru-RU');
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    var parts = iso.split('-');
    if (parts.length === 3) return parts[2] + '.' + parts[1] + '.' + parts[0];
    return iso;
  }

  /* ── Отчёты: уровень центров ─────────────────────────────────────────── */

  function renderCentersTables(el, data) {
    var centers = data.centers || [];
    if (!centers.length) {
      el.innerHTML = '<div class="an-empty"><i class="fas fa-sitemap"></i>Нет данных</div>';
      return;
    }

    var html = _rptSummaryCards(data);

    html += '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-city"></i> По центрам <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge">' + centers.length + ' центров</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';
    html += _rptUnitTable(centers, 'Центр', 'code', function (c) {
      return 'anDrillCenter(' + c.id + ')';
    });
    html += '</div></div>';

    html += _rptProjectsBlock(data);
    html += _rptDebtsBlock(data);

    el.innerHTML = html;
  }

  function _renderCentersSummary(data, centers) {
    var planned = data.total_planned || 0;
    var norm = data.total_norm || 0;
    var load = data.total_load_pct || 0;
    var loadCls = loadBadgeCls(load);
    var colorMap = { ok: 'an-val-green', warn: 'an-val-yellow', over: 'an-val-red' };
    var totalEmps = 0;
    centers.forEach(function (c) {
      totalEmps += c.employee_count || 0;
    });

    var html = '<div class="an-summary">';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
      centers.length +
      '</div><div class="an-summary-label">Центров</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
      totalEmps +
      '</div><div class="an-summary-label">Сотрудников</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
      fmtHrs(planned) +
      '</div><div class="an-summary-label">План (ч)</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val">' +
      fmtHrs(norm) +
      '</div><div class="an-summary-label">Норма (ч)</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val ' +
      (colorMap[loadCls] || '') +
      '">' +
      fmtPct(load) +
      '</div><div class="an-summary-label">Загрузка</div></div>';
    html += '</div>';
    return html;
  }

  /* ── Уровень отделов (charts) ────────────────────────────────────────── */

  function renderAllDeptsCharts(el, data) {
    var depts = data.depts || [];
    if (!depts.length) {
      el.innerHTML =
        '<div class="an-empty"><i class="fas fa-building"></i>Нет данных по отделам</div>';
      return;
    }

    var html = renderSummaryCards(data);

    html += '<div class="an-widgets">';
    html +=
      '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
    html += '</div>';

    html += '<div class="an-widget an-widget-full" style="padding:0;">';
    html +=
      '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-building"></i> Отделы</div>';
    html += '<div style="overflow-x:auto;padding:0 12px 10px;">';
    html += '<table class="an-list-table"><thead><tr>';
    html += '<th>Отдел</th><th>Название</th><th class="cell-num">Сотрудников</th>';
    html +=
      '<th class="cell-num">План (ч)</th><th class="cell-num">Норма (ч)</th><th class="cell-num">Загрузка</th>';
    html += '</tr></thead><tbody>';

    depts.forEach(function (d) {
      var badgeCls = loadBadgeCls(d.total_load_pct);
      html += '<tr onclick="anDrillDept(\'' + escAttr(d.code) + '\')">';
      html += '<td><strong>' + esc(d.code) + '</strong></td>';
      html += '<td>' + esc(d.name) + '</td>';
      html += '<td class="cell-num">' + (d.employee_count || 0) + '</td>';
      html += '<td class="cell-num">' + fmtHrs(d.total_planned) + '</td>';
      html += '<td class="cell-num">' + fmtHrs(d.total_norm) + '</td>';
      html +=
        '<td class="cell-num"><span class="an-load-badge ' +
        badgeCls +
        '">' +
        fmtPct(d.total_load_pct) +
        '</span></td>';
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';

    // Drilldown: сотрудники по отделам
    depts.forEach(function (d) {
      (d.sectors || []).forEach(function (s) {
        if (s.employees && s.employees.length > 0) {
          html += renderEmployeesList(s.employees, esc(d.code) + ' — ' + esc(s.name));
        }
      });
    });

    el.innerHTML = html;
    renderBarChart(data.months || []);
  }

  function renderDeptCharts(el, data) {
    var sectors = data.sectors || [];
    var html = renderSummaryCards(data);

    html += '<div class="an-widgets">';
    html +=
      '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
    html += '</div>';

    if (sectors.length > 0) {
      html += '<div class="an-widget an-widget-full" style="padding:0;">';
      html +=
        '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-layer-group"></i> Секторы</div>';
      html += '<div style="overflow-x:auto;padding:0 12px 10px;">';
      html += '<table class="an-list-table"><thead><tr>';
      html += '<th>Сектор</th><th class="cell-num">Сотрудников</th>';
      html +=
        '<th class="cell-num">План (ч)</th><th class="cell-num">Норма (ч)</th><th class="cell-num">Загрузка</th>';
      html += '</tr></thead><tbody>';

      sectors.forEach(function (s) {
        var badgeCls = loadBadgeCls(s.total_load_pct);
        var empCount = (s.employees || []).length;
        html += '<tr onclick="anDrillSector(' + s.id + ')">';
        html += '<td><strong>' + esc(s.name) + '</strong></td>';
        html += '<td class="cell-num">' + empCount + '</td>';
        html += '<td class="cell-num">' + fmtHrs(s.total_planned) + '</td>';
        html += '<td class="cell-num">' + fmtHrs(s.total_norm) + '</td>';
        html +=
          '<td class="cell-num"><span class="an-load-badge ' +
          badgeCls +
          '">' +
          fmtPct(s.total_load_pct) +
          '</span></td>';
        html += '</tr>';
      });
      html += '</tbody></table></div></div>';
    }

    sectors.forEach(function (s) {
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
    html +=
      '<div class="an-widget an-widget-full"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
    html += '</div>';

    html += renderEmployeesList(
      employees,
      data.view === 'employees' ? 'Выбранные сотрудники' : 'Сотрудники сектора',
    );

    el.innerHTML = html;
    renderBarChart(data.months || []);
  }

  function renderEmployeeCharts(el, data) {
    var emp = data.employee || {};
    var empLabel = emp.name ? ' ' + esc(emp.name) : '';
    var html = renderSummaryCards(data);

    html += '<div class="an-widgets">';
    html +=
      '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-chart-bar"></i> Загрузка по месяцам' +
      (empLabel ? ':' + empLabel : '') +
      '</div><div class="an-chart-wrap"><canvas id="anChart"></canvas></div></div>';
    html +=
      '<div class="an-widget"><div class="an-widget-title"><i class="fas fa-calendar-alt"></i> Помесячная разбивка' +
      (empLabel ? ':' + empLabel : '') +
      '</div>';
    html += renderMonthsTable(data.months || []);
    html += '</div></div>';

    html += renderTasksBlock(data);

    el.innerHTML = html;
    _anInitTaskSort();
    renderBarChart(data.months || []);
  }

  /* ═══════════════════════════════════════════════════════════════════════
   РЕЖИМ «ТАБЛИЦЫ» — карточки + таблицы + экспорт (из reports.js)
   ═══════════════════════════════════════════════════════════════════════ */

  /* ── Сводка по задачам (НТЦ / отдел) ──────────────────────────────────── */
  function renderWorksSummary(data) {
    var s = data.summary;
    if (!s) return '';

    var html = '<div class="rpt-tasks-wrap" style="margin-bottom:16px;">';
    html +=
      '<div class="rpt-tasks-header"><div class="rpt-tasks-title"><i class="fas fa-clipboard-list"></i> Сводка по задачам</div></div>';
    html += '<div style="padding:0 20px 16px;">';

    var totalAll = s.planned_count + s.overdue_count;
    var allItems = (s.planned || []).concat(s.overdue || []);

    var sections = [
      {
        key: 'total',
        label: 'Всего работ',
        count: totalAll,
        items: allItems,
        icon: 'fa-list',
        color: 'var(--text)',
      },
      {
        key: 'planned',
        label: 'Работ запланировано',
        count: s.planned_count,
        items: s.planned,
        icon: 'fa-calendar-check',
        color: 'var(--accent)',
      },
      {
        key: 'overdue',
        label: 'Ранее просроченных',
        count: s.overdue_count,
        items: s.overdue,
        icon: 'fa-exclamation-triangle',
        color: 'var(--danger)',
      },
      {
        key: 'done',
        label: 'Выполнено',
        count: s.done_count,
        items: s.done,
        icon: 'fa-check-circle',
        color: '#16a34a',
      },
      {
        key: 'not_done',
        label: 'Не выполнено',
        count: s.not_done_count,
        items: s.not_done,
        icon: 'fa-clock',
        color: '#d97706',
      },
    ];

    sections.forEach(function (sec) {
      html += '<div class="an-summary-section" style="margin-bottom:8px;">';
      html +=
        '<div class="an-summary-toggle" onclick="this.classList.toggle(\'open\');this.nextElementSibling.classList.toggle(\'collapsed\');" style="cursor:pointer;display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);">';
      html +=
        '<i class="fas fa-chevron-right" style="font-size:10px;transition:transform 0.2s;"></i>';
      html +=
        '<i class="fas ' +
        sec.icon +
        '" style="color:' +
        sec.color +
        ';width:16px;text-align:center;"></i>';
      html += '<span style="font-weight:600;font-size:13px;">' + sec.label + '</span>';
      html +=
        '<span style="font-weight:700;font-size:14px;color:' +
        sec.color +
        ';">' +
        sec.count +
        '</span>';
      html += '</div>';
      html += '<div class="an-summary-body collapsed" style="padding:4px 0 4px 24px;">';

      if (sec.items && sec.items.length > 0) {
        // Сортировка по сроку по умолчанию
        var sortedItems = sec.items.slice().sort(function (a, b) {
          var da = a.deadline || a.date_end || '9999-12-31';
          var db = b.deadline || b.date_end || '9999-12-31';
          return da.localeCompare(db);
        });
        var tableId = 'an-summary-table-' + sec.key;
        html += '<table id="' + tableId + '" class="an-tasks-table">';
        html += '<thead><tr>';
        html +=
          '<th data-sort="work_name" style="text-align:left;padding:2px 6px;color:var(--muted);cursor:pointer;">Задача</th>';
        html +=
          '<th data-sort="project_name" style="text-align:left;padding:2px 6px;color:var(--muted);cursor:pointer;">Проект</th>';
        html +=
          '<th data-sort="executor" style="text-align:left;padding:2px 6px;color:var(--muted);cursor:pointer;">Исполнитель</th>';
        html +=
          '<th data-sort="deadline" style="text-align:left;padding:2px 6px;color:var(--muted);cursor:pointer;">Срок</th>';
        html += '</tr></thead><tbody>';
        var todayStr = new Date().toISOString().slice(0, 7); // YYYY-MM
        sortedItems.forEach(function (t) {
          var dlF = t.deadline
            ? t.deadline.slice(8, 10) + '.' + t.deadline.slice(5, 7) + '.' + t.deadline.slice(0, 4)
            : '—';
          var dlMonth = (t.deadline || t.date_end || '').slice(0, 7);
          var rowCls =
            t.status === 'overdue'
              ? ' class="an-row-overdue"'
              : dlMonth > todayStr
                ? ' class="an-row-future"'
                : '';
          html += '<tr' + rowCls + '>';
          html += '<td style="padding:2px 6px;">' + esc(t.work_name) + '</td>';
          html += '<td style="padding:2px 6px;">' + esc(t.project_name || '') + '</td>';
          html += '<td style="padding:2px 6px;">' + esc(t.executor || '') + '</td>';
          html += '<td style="padding:2px 6px;white-space:nowrap;">' + dlF + '</td>';
          html += '</tr>';
        });
        html += '</tbody></table>';
      } else {
        html += '<div style="color:var(--muted);padding:4px 0;">Нет</div>';
      }

      html += '</div></div>';
    });

    html += '</div></div>';

    // CSS для toggle
    html += '<style>';
    html += '.an-summary-toggle .fa-chevron-right { transform:rotate(0); }';
    html += '.an-summary-toggle.open .fa-chevron-right { transform:rotate(90deg); }';
    html += '.an-summary-body.collapsed { display:none; }';
    html += '</style>';

    return html;
  }

  var _anSummarySortStates = {};

  function _initSummarySort() {
    var tables = document.querySelectorAll('[id^="an-summary-table-"]');
    tables.forEach(function (table) {
      var key = table.id;
      if (!_anSummarySortStates[key]) {
        _anSummarySortStates[key] = { col: 'deadline', dir: 'asc' };
      }
      var state = _anSummarySortStates[key];
      var thead = table.querySelector('thead');
      if (!thead) return;
      renderSortIndicators(thead, state);
      thead.querySelectorAll('th[data-sort]').forEach(function (th) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.onclick = function () {
          toggleSort(state, th.getAttribute('data-sort'));
          // Пересортировать строки
          var tbody = table.querySelector('tbody');
          var rows = Array.from(tbody.querySelectorAll('tr'));
          var colIdx = { work_name: 0, project_name: 1, executor: 2, deadline: 3 };
          var idx = colIdx[state.col] || 0;
          var dir = state.dir === 'desc' ? -1 : 1;
          rows.sort(function (a, b) {
            var va = a.cells[idx] ? a.cells[idx].textContent.trim() : '';
            var vb = b.cells[idx] ? b.cells[idx].textContent.trim() : '';
            return va.localeCompare(vb, 'ru') * dir;
          });
          rows.forEach(function (r) {
            tbody.appendChild(r);
          });
          renderSortIndicators(thead, state);
        };
      });
    });
  }

  function renderAllDeptsTables(el, data) {
    var depts = data.depts || [];
    if (!depts.length) {
      el.innerHTML =
        '<div class="an-empty"><i class="fas fa-building"></i>Нет данных по отделам</div>';
      return;
    }

    var html = _rptSummaryCards(data);

    html += '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-building"></i> По отделам <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge">' + depts.length + ' отделов</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';
    html += _rptUnitTable(depts, 'Отдел', 'code', function (d) {
      return "anDrillDept('" + escAttr(d.code) + "')";
    });
    html += '</div></div>';

    html += _rptProjectsBlock(data);
    html += _rptDebtsBlock(data);

    el.innerHTML = html;
  }

  function renderDeptTables(el, data) {
    var sectors = data.sectors || [];
    var deptName = data.dept ? data.dept.name || data.dept.code : '';

    var html = _rptSummaryCards(data);

    html += '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-layer-group"></i> ' +
      esc(deptName) +
      ' — Секторы <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge">' + sectors.length + ' секторов</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';

    if (sectors.length === 0) {
      html += '<div class="an-empty"><i class="fas fa-layer-group"></i>Нет секторов</div>';
    } else {
      html += _rptUnitTable(sectors, 'Сектор', 'name', function (s) {
        return 'anDrillSector(' + s.id + ')';
      });
    }
    html += '</div></div>';

    html += _rptProjectsBlock(data);
    html += _rptDebtsBlock(data);

    el.innerHTML = html;
  }

  function renderSectorTables(el, data) {
    var employees = data.employees || [];
    var title = data.view === 'employees' ? 'Выбранные сотрудники' : 'Сотрудники сектора';

    var html = _rptSummaryCards(data);

    html += '<div class="rpt-section collapsed">';
    html +=
      '<div class="rpt-section-header rpt-collapsible" onclick="this.parentElement.classList.toggle(\'collapsed\')">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-users"></i> ' +
      esc(title) +
      ' <i class="fas fa-chevron-down rpt-collapse-icon"></i></div>';
    html += '<span class="rpt-badge">' + employees.length + ' сотрудников</span>';
    html += '</div>';
    html += '<div class="rpt-section-body">';

    if (employees.length > 0) {
      html += _rptUnitTable(employees, 'Сотрудник', 'name', function (e) {
        return 'anDrillEmployee(' + e.id + ')';
      });
    } else {
      html += '<div class="an-empty"><i class="fas fa-users"></i>Нет сотрудников</div>';
    }
    html += '</div></div>';

    html += _rptDebtsBlock(data);

    el.innerHTML = html;
  }

  function renderEmployeeTables(el, data) {
    var emp = data.employee || {};
    var tasks = data.tasks || [];

    var html = _rptSummaryCards(data);

    // Таблица задач
    html += '<div class="rpt-section">';
    html += '<div class="rpt-section-header">';
    html +=
      '<div class="rpt-section-title"><i class="fas fa-tasks"></i> Задачи' +
      (emp.name ? ': ' + esc(emp.name) : '') +
      '</div>';
    html += '<span class="rpt-badge">' + tasks.length + ' задач</span>';
    html += '</div>';

    if (tasks.length > 0) {
      html += '<table class="rpt-tbl">';
      html += '<thead><tr><th>№</th><th>Задача</th><th>Проект</th>';
      html += '<th class="num">Срок</th><th class="num">План (ч)</th><th>Статус</th></tr></thead>';
      html += '<tbody>';
      tasks.forEach(function (t, i) {
        html += '<tr>';
        html += '<td class="muted">' + (i + 1) + '</td>';
        html += '<td class="bold">' + esc(t.work_name) + '</td>';
        html += '<td>' + esc(t.project_name || '') + '</td>';
        html += '<td class="num">' + fmtDate(t.date_end) + '</td>';
        html += '<td class="num">' + fmtHrs(t.plan_hours || 0) + '</td>';
        html += '<td>' + _rptStatusBadge(t.status, t.days_overdue) + '</td>';
        html += '</tr>';
      });
      html += '</tbody></table>';
    } else {
      html += '<div class="an-empty"><i class="fas fa-tasks"></i>Нет задач</div>';
    }
    html += '</div>';

    el.innerHTML = html;
  }

  /* ═══════════════════════════════════════════════════════════════════════
   ОБЩИЕ КОМПОНЕНТЫ
   ═══════════════════════════════════════════════════════════════════════ */

  function renderSummaryCards(data) {
    var planned = data.total_planned || 0;
    var norm = data.total_norm || 0;
    var load = data.total_load_pct || 0;
    var loadCls = loadBadgeCls(load);
    var colorMap = { ok: 'an-val-green', warn: 'an-val-yellow', over: 'an-val-red' };

    var empCount = data.employee_count || 0;

    var html = '<div class="an-summary">';
    if (empCount > 0) {
      html +=
        '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
        empCount +
        '</div><div class="an-summary-label">Сотрудников</div></div>';
    }
    html +=
      '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
      fmtHrs(planned) +
      '</div><div class="an-summary-label">План (ч)</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val">' +
      fmtHrs(norm) +
      '</div><div class="an-summary-label">Норма (ч)</div></div>';
    html +=
      '<div class="an-summary-card"><div class="an-summary-val ' +
      (colorMap[loadCls] || '') +
      '">' +
      fmtPct(load) +
      '</div><div class="an-summary-label">Загрузка</div></div>';

    if (data.tasks) {
      html +=
        '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
        data.tasks.length +
        '</div><div class="an-summary-label">Задач</div></div>';
    } else if (data.view === 'all') {
      var depts = data.depts || [];
      html +=
        '<div class="an-summary-card"><div class="an-summary-val an-val-accent">' +
        depts.length +
        '</div><div class="an-summary-label">Отделов</div></div>';
    }

    html += '</div>';
    return html;
  }

  function renderEmployeesList(employees, title) {
    if (!employees || !employees.length) return '';

    var html = '<div class="an-widget an-widget-full" style="padding:0;">';
    html +=
      '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-users"></i> ' +
      (title || 'Сотрудники') +
      '</div>';
    html += '<div style="overflow-x:auto;padding:0 12px 10px;">';
    html += '<table class="an-list-table"><thead><tr>';
    html += '<th>Сотрудник</th>';
    for (var m = 1; m <= 12; m++) {
      html += '<th class="cell-num">' + MONTHS_SHORT[m] + '</th>';
    }
    html += '<th class="cell-num">Итого</th><th class="cell-num">Загрузка</th>';
    html += '</tr></thead><tbody>';

    employees.forEach(function (e) {
      var badgeCls = loadBadgeCls(e.total_load_pct);
      html += '<tr onclick="anDrillEmployee(' + e.id + ')">';
      html += '<td><strong>' + esc(e.name) + '</strong></td>';

      var months = e.months || [];
      var monthMap = {};
      months.forEach(function (md) {
        monthMap[md.month] = md;
      });
      for (var m = 1; m <= 12; m++) {
        var planned = monthMap[m] ? monthMap[m].planned : 0;
        html += '<td class="cell-num">' + (planned > 0 ? planned.toFixed(1) : '') + '</td>';
      }

      html += '<td class="cell-num"><strong>' + fmtHrs(e.total_planned) + '</strong></td>';
      html +=
        '<td class="cell-num"><span class="an-load-badge ' +
        badgeCls +
        '">' +
        fmtPct(e.total_load_pct) +
        '</span></td>';
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';
    return html;
  }

  /* Таблица сотрудников для табличного режима */
  function _renderEmpTable(employees, title) {
    if (!employees || !employees.length) return '';
    var html = '<div class="rpt-tasks-wrap" style="margin-top:10px;">';
    if (title) {
      html +=
        '<div class="rpt-tasks-header"><div class="rpt-tasks-title"><i class="fas fa-users"></i> ' +
        title +
        '</div></div>';
    }
    html += '<div style="overflow-x:auto;padding:0 12px 10px;">';
    html += '<table class="an-list-table">';
    html += '<colgroup><col style="width:140px;">';
    for (var m = 1; m <= 12; m++) html += '<col style="width:56px;">';
    html += '<col style="width:64px;"><col style="width:68px;">';
    html += '</colgroup>';
    html += '<thead><tr>';
    html += '<th>Сотрудник</th>';
    for (let m = 1; m <= 12; m++) html += '<th class="cell-num">' + MONTHS_SHORT[m] + '</th>';
    html += '<th class="cell-num">Итого</th><th class="cell-num">Загрузка</th>';
    html += '</tr></thead><tbody>';

    employees.forEach(function (e) {
      var badgeCls = loadBadgeCls(e.total_load_pct);
      html += '<tr onclick="anDrillEmployee(' + e.id + ')">';
      html += '<td><strong>' + esc(e.name) + '</strong></td>';
      var monthMap = {};
      (e.months || []).forEach(function (md) {
        monthMap[md.month] = md;
      });
      for (var m = 1; m <= 12; m++) {
        var planned = monthMap[m] ? monthMap[m].planned : 0;
        html += '<td class="cell-num">' + (planned > 0 ? planned.toFixed(1) : '') + '</td>';
      }
      html += '<td class="cell-num"><strong>' + fmtHrs(e.total_planned) + '</strong></td>';
      html +=
        '<td class="cell-num"><span class="an-load-badge ' +
        badgeCls +
        '">' +
        fmtPct(e.total_load_pct) +
        '</span></td>';
      html += '</tr>';
    });

    html += '</tbody></table></div></div>';
    return html;
  }

  function renderMonthsTable(months) {
    var html =
      '<table class="an-months-table"><thead><tr><th></th><th>План</th><th>Норма</th><th>Загрузка</th></tr></thead><tbody>';

    months.forEach(function (m) {
      var badgeCls = loadBadgeCls(m.load_pct);
      html += '<tr>';
      html += '<td class="row-label">' + MONTHS_SHORT[m.month || 1] + '</td>';
      html += '<td>' + fmtHrs(m.planned) + '</td>';
      html += '<td>' + fmtHrs(m.norm) + '</td>';
      html +=
        '<td><span class="an-load-badge ' + badgeCls + '">' + fmtPct(m.load_pct) + '</span></td>';
      html += '</tr>';
    });

    html += '</tbody></table>';
    return html;
  }

  /* Блок задач для графического режима (employee view) */
  function renderTasksBlock(data) {
    var tasks = data.tasks || [];
    var emp = data.employee || {};
    var html = '<div class="an-widget an-widget-full" style="padding:0;">';
    html +=
      '<div class="an-widget-title" style="padding:20px 20px 0;"><i class="fas fa-tasks"></i> Задачи' +
      (emp.name ? ': ' + esc(emp.name) : '') +
      ' (' +
      tasks.length +
      ')';
    html += '<span class="an-legend"><span class="an-active-mark"></span> период выполнения';
    html += ' &nbsp; <span class="an-abs-mark an-abs-vac"></span> отпуск';
    html += ' &nbsp; <span class="an-abs-mark an-abs-trip"></span> командировка</span>';
    html += '</div>';

    html += renderTasksTableBody(data);
    html += '</div>';
    return html;
  }

  /* ── Сортировка таблицы задач в аналитике ──────────────────────────────── */
  var _anTaskSortState = { col: 'date_end', dir: 'asc' };
  var _anTaskData = null;

  function _anInitTaskSort() {
    var table = document.querySelector('.an-tasks-table');
    if (!table) return;
    var thead = table.querySelector('thead');
    if (!thead) return;
    thead.querySelectorAll('th[data-sort]').forEach(function (th) {
      th.style.cursor = 'pointer';
      th.style.userSelect = 'none';
      th.addEventListener('click', function () {
        toggleSort(_anTaskSortState, th.getAttribute('data-sort'));
        // Перерендерить только тело таблицы
        if (_anTaskData) {
          var wrapper = table.closest('.rpt-tasks-wrap') || table.closest('.an-widget-full');
          if (wrapper) {
            var oldTable = wrapper.querySelector('.an-tasks-table');
            if (oldTable) {
              var tmp = document.createElement('div');
              tmp.innerHTML = renderTasksTableBody(_anTaskData);
              var newTable = tmp.querySelector('.an-tasks-table');
              if (newTable) oldTable.parentNode.replaceChild(newTable, oldTable);
              _anInitTaskSort(); // переинициализировать на новой таблице
            }
          }
        }
      });
    });
    renderSortIndicators(thead, _anTaskSortState);
  }

  /* Общее тело таблицы задач (используется в обоих режимах) */
  function renderTasksTableBody(data) {
    _anTaskData = data;
    var tasks = (data.tasks || []).slice();
    // Применяем сортировку
    tasks = applySortToArray(tasks, _anTaskSortState, function (t, col) {
      if (col === '_total') {
        var sum = 0;
        if (t.plan_hours) {
          for (var k in t.plan_hours) sum += parseFloat(t.plan_hours[k]) || 0;
        }
        return sum;
      }
      if (col === 'project_name') return t.project_name || t.project || '';
      return t[col] || '';
    });
    var selYears = idsToList(currentYears);
    var today = new Date().toISOString().slice(0, 10);

    if (tasks.length === 0) {
      return '<div class="an-empty"><i class="fas fa-clipboard-check"></i>Нет задач</div>';
    }

    var absences = data.absences || [];
    var absMonths = {};
    absences.forEach(function (a) {
      var dsLabel = a.date_start ? a.date_start.slice(8, 10) + '.' + a.date_start.slice(5, 7) : '';
      var deLabel = a.date_end ? a.date_end.slice(8, 10) + '.' + a.date_end.slice(5, 7) : '';
      var fullLabel = a.label + ': ' + dsLabel + ' – ' + deLabel;
      selYears.forEach(function (y) {
        var yInt = parseInt(y);
        var ds = new Date(a.date_start);
        var de = new Date(a.date_end);
        for (var mm = 1; mm <= 12; mm++) {
          var mStart = new Date(yInt, mm - 1, 1);
          var mEnd = new Date(yInt, mm, 0);
          if (mEnd >= ds && mStart <= de) {
            if (!absMonths[mm]) absMonths[mm] = { vac: false, trip: false, titles: [] };
            if (a.type === 'vacation') absMonths[mm].vac = true;
            else absMonths[mm].trip = true;
            if (absMonths[mm].titles.indexOf(fullLabel) === -1)
              absMonths[mm].titles.push(fullLabel);
          }
        }
      });
    });

    var html = '<div style="overflow-x:auto;padding:0 12px 10px;">';
    html += '<table class="an-tasks-table"><thead><tr>';
    html +=
      '<th data-sort="work_name">Название</th><th data-sort="project_name">Проект</th><th data-sort="date_start">Начало</th><th data-sort="date_end">Окончание</th><th data-sort="deadline">Срок выполнения</th>';
    for (var m = 1; m <= 12; m++) {
      html +=
        '<th class="cell-num" title="Плановые часы / период выполнения задачи">' +
        MONTHS_SHORT[m] +
        '</th>';
    }
    html +=
      '<th class="cell-num" data-sort="_total">Итого (ч)</th><th data-sort="status">Статус</th>';
    html += '</tr></thead><tbody>';

    if (absences.length > 0) {
      html += '<tr class="an-absence-row">';
      html +=
        '<td colspan="5" style="font-weight:600;color:var(--muted);"><i class="fas fa-plane-departure" style="margin-right:4px;"></i>Отпуска / командировки</td>';
      for (let m = 1; m <= 12; m++) {
        var info = absMonths[m];
        if (info) {
          var marks = '';
          if (info.vac) marks += '<span class="an-abs-mark an-abs-vac"></span>';
          if (info.trip) marks += '<span class="an-abs-mark an-abs-trip"></span>';
          var bgCls = info.vac ? 'an-cell-vac' : 'an-cell-trip';
          html +=
            '<td class="cell-num ' +
            bgCls +
            '" title="' +
            esc(info.titles.join('; ')) +
            '">' +
            marks +
            '</td>';
        } else {
          html += '<td class="cell-num"></td>';
        }
      }
      html += '<td class="cell-num"></td><td></td></tr>';
    }

    tasks.forEach(function (t) {
      var dsF = t.date_start
        ? t.date_start.slice(8, 10) +
          '.' +
          t.date_start.slice(5, 7) +
          '.' +
          t.date_start.slice(0, 4)
        : '—';
      var deF = t.date_end
        ? t.date_end.slice(8, 10) + '.' + t.date_end.slice(5, 7) + '.' + t.date_end.slice(0, 4)
        : '—';
      var dlRaw = t.date_end || t.deadline || '';
      var dlF = dlRaw
        ? dlRaw.slice(8, 10) + '.' + dlRaw.slice(5, 7) + '.' + dlRaw.slice(0, 4)
        : '—';
      var statusCls = 'an-badge-status an-badge-' + t.status;
      var statusText =
        t.status === 'done' ? 'Готово' : t.status === 'overdue' ? 'Просроч.' : 'В работе';

      var activeMonths = {};
      if (t.date_start) {
        selYears.forEach(function (y) {
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

      var isOverdue =
        t.status === 'overdue' || (t.date_end && t.date_end < today && t.status !== 'done');
      html += '<tr class="' + (isOverdue ? 'an-row-overdue' : '') + '">';
      html += '<td>' + esc(t.work_name) + '</td>';
      html += '<td>' + esc(t.project_name || t.project) + '</td>';
      html += '<td style="white-space:nowrap">' + dsF + '</td>';
      html += '<td style="white-space:nowrap">' + deF + '</td>';
      html += '<td style="white-space:nowrap">' + dlF + '</td>';

      var rowTotal = 0;
      var hasPlanHours = false;
      if (t.plan_hours) {
        for (var k in t.plan_hours) {
          if (t.plan_hours[k]) {
            hasPlanHours = true;
            break;
          }
        }
      }

      for (var m = 1; m <= 12; m++) {
        var hrs = 0;
        selYears.forEach(function (y) {
          var key = y + '-' + (m < 10 ? '0' + m : m);
          if (t.plan_hours && t.plan_hours[key]) hrs += parseFloat(t.plan_hours[key]);
        });
        rowTotal += hrs;
        var absInfo = absMonths[m];
        var absCls = absInfo
          ? absInfo.vac && absInfo.trip
            ? ' an-cell-vac an-cell-trip'
            : absInfo.vac
              ? ' an-cell-vac'
              : ' an-cell-trip'
          : '';
        var absTitle = absInfo ? ' title="' + esc(absInfo.titles.join('; ')) + '"' : '';
        if (hrs > 0) {
          html += '<td class="cell-num' + absCls + '"' + absTitle + '>' + hrs.toFixed(1) + '</td>';
        } else if (!hasPlanHours && activeMonths[m]) {
          html +=
            '<td class="cell-num' +
            absCls +
            '"' +
            absTitle +
            '><span class="an-active-mark" title="Период выполнения"></span></td>';
        } else {
          html += '<td class="cell-num' + absCls + '"' + absTitle + '></td>';
        }
      }
      html +=
        '<td class="cell-num"><strong>' +
        (rowTotal > 0 ? rowTotal.toFixed(1) : '') +
        '</strong></td>';
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

    var planned = months.map(function (m) {
      return m.planned;
    });
    var norms = months.map(function (m) {
      return m.norm;
    });

    chartBar = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: MONTHS_SHORT_0,
        datasets: [
          {
            label: 'План (ч)',
            data: planned,
            backgroundColor: accent + '88',
            borderColor: accent,
            borderWidth: 1,
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
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { font: { size: 12 }, color: getCSSVar('--text') || '#333' },
          },
        },
        scales: {
          x: { ticks: { color: muted }, grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { color: muted },
            grid: { color: getCSSVar('--border') || '#eee' },
          },
        },
      },
    });
  }

  /* ── Экспорт ──────────────────────────────────────────────────────────── */
  function _summaryExportData(data) {
    var s = data.summary;
    if (!s) return [];
    // «Всего работ» = planned + overdue (без done)
    var all = (s.planned || []).concat(s.overdue || []);
    // Дедупликация по id
    var seen = {};
    var result = [];
    all.forEach(function (t) {
      if (seen[t.id]) return;
      seen[t.id] = true;
      result.push({
        work_name: t.work_name || '',
        project_name: t.project_name || '',
        executor: t.executor || '',
        deadline: t.deadline || t.date_end || '',
        status: t.status === 'done' ? 'Готово' : t.status === 'overdue' ? 'Просрочено' : 'В работе',
      });
    });
    result.sort(function (a, b) {
      var da = a.deadline || '9999-12-31';
      var db = b.deadline || '9999-12-31';
      return da.localeCompare(db);
    });
    return result;
  }

  function _summaryExportCols() {
    return [
      { key: 'work_name', header: 'Задача', width: 260 },
      { key: 'project_name', header: 'Проект', width: 140 },
      { key: 'executor', header: 'Исполнитель', width: 160 },
      { key: 'deadline', header: 'Срок', width: 100 },
      { key: 'status', header: 'Статус', width: 80 },
    ];
  }

  function _deptExportCols() {
    return [
      { key: 'dept_code', header: 'Код отдела', width: 80, forceText: true },
      { key: 'dept_name', header: 'Название', width: 200 },
      { key: 'employees', header: 'Сотрудников', width: 100 },
      { key: 'planned', header: 'План (ч)', width: 100 },
      { key: 'norm', header: 'Норма (ч)', width: 100 },
      {
        key: 'load_pct',
        header: 'Загрузка (%)',
        width: 100,
        format: function (r) {
          return r.load_pct.toFixed(1);
        },
      },
    ];
  }

  function _empExportRow(e, deptCode, sectorName) {
    var row = {
      dept: deptCode,
      sector: sectorName,
      name: e.name,
      planned: e.total_planned || 0,
      norm: e.total_norm || 0,
      load_pct: e.total_load_pct || 0,
    };
    var monthMap = {};
    (e.months || []).forEach(function (md) {
      monthMap[md.month] = md;
    });
    for (var m = 1; m <= 12; m++) {
      row['m' + m] = monthMap[m] ? monthMap[m].planned : 0;
    }
    return row;
  }

  function _empExportCols() {
    var cols = [
      { key: 'dept', header: 'Отдел', width: 80, forceText: true },
      { key: 'sector', header: 'Сектор', width: 120 },
      { key: 'name', header: 'Сотрудник', width: 180 },
    ];
    for (var m = 1; m <= 12; m++) {
      cols.push({ key: 'm' + m, header: MONTHS_SHORT[m], width: 60 });
    }
    cols.push({ key: 'planned', header: 'Итого (ч)', width: 80 });
    cols.push({
      key: 'load_pct',
      header: 'Загрузка (%)',
      width: 80,
      format: function (r) {
        return r.load_pct.toFixed(1);
      },
    });
    return cols;
  }

  function _taskExportCols() {
    var cols = [
      { key: 'work_name', header: 'Название', width: 240 },
      { key: 'project', header: 'Проект', width: 140 },
      { key: 'date_start', header: 'Начало', width: 100 },
      { key: 'date_end', header: 'Окончание', width: 100 },
    ];
    for (var m = 1; m <= 12; m++) {
      cols.push({ key: 'm' + m, header: MONTHS_SHORT[m], width: 60 });
    }
    cols.push({ key: 'total_hours', header: 'Итого (ч)', width: 80 });
    cols.push({ key: 'status', header: 'Статус', width: 80 });
    return cols;
  }

  /* ── Подготовка данных для экспорта ───────────────────────────────────── */

  function _unitExportCols(label) {
    return [
      { key: 'name', header: label, width: 200 },
      { key: 'employee_count', header: 'Сотрудников', width: 100 },
      { key: 'total', header: 'Задач', width: 80 },
      { key: 'done', header: 'Выполнено', width: 100 },
      { key: 'overdue', header: 'Просрочено', width: 100 },
      { key: 'debts_total', header: 'Долги', width: 80 },
      { key: 'plan_hours', header: 'План (ч)', width: 100 },
      { key: 'norm_hours', header: 'Норма (ч)', width: 100 },
      {
        key: 'completion_pct',
        header: 'Выполнение (%)',
        width: 100,
        format: function (r) {
          return (r.completion_pct || 0).toFixed(1);
        },
      },
    ];
  }

  function _unitExportData(items, nameKey) {
    return (items || []).map(function (item) {
      return {
        name: item[nameKey] || item.code || item.name || '',
        employee_count: item.employee_count || 0,
        total: item.total || 0,
        done: item.done || 0,
        overdue: item.overdue || 0,
        debts_total: item.debts_total || 0,
        plan_hours: item.plan_hours || 0,
        norm_hours: item.norm_hours || 0,
        completion_pct: item.completion_pct || 0,
      };
    });
  }

  function _taskExportData(tasks) {
    return (tasks || []).map(function (t) {
      var statusMap = { done: 'Готово', overdue: 'Просрочено', inwork: 'В работе', debt: 'Долг' };
      return {
        work_name: t.work_name || '',
        project_name: t.project_name || '',
        date_end: t.date_end || '',
        plan_hours: t.plan_hours || 0,
        status: statusMap[t.status] || t.status || '',
      };
    });
  }

  function _taskExportColsSimple() {
    return [
      { key: 'work_name', header: 'Задача', width: 260 },
      { key: 'project_name', header: 'Проект', width: 160 },
      { key: 'date_end', header: 'Срок', width: 100 },
      { key: 'plan_hours', header: 'План (ч)', width: 80 },
      { key: 'status', header: 'Статус', width: 100 },
    ];
  }

  function _exportMeta(data) {
    var parts = [];
    var mode = currentMode === 'charts' ? 'Личный план' : 'Отчёты';
    parts.push(mode);
    var years = Object.keys(currentYears);
    if (years.length) parts.push('Период: ' + years.join(', '));
    if (data.center) parts.push('Центр: ' + (data.center.name || data.center.code));
    if (data.dept) parts.push('Отдел: ' + (data.dept.name || data.dept.code));
    if (data.sector)
      parts.push('Сектор: ' + (data.sector.name || data.sector.code || data.sector.id));
    if (data.employee) parts.push('Сотрудник: ' + (data.employee.name || ''));
    return parts;
  }

  function _setupExport(data) {
    var cols, pageName;
    var view = data.view;
    var mode = currentMode === 'charts' ? 'План' : 'Отчёты';

    switch (view) {
      case 'centers':
        _exportData = _unitExportData(data.centers, 'code');
        cols = _unitExportCols('Центр');
        pageName = mode + '_Центры';
        break;
      case 'all':
        _exportData = _unitExportData(data.depts, 'code');
        cols = _unitExportCols('Отдел');
        pageName = mode + '_Отделы';
        break;
      case 'dept':
        _exportData = _unitExportData(data.sectors, 'name');
        cols = _unitExportCols('Сектор');
        pageName = mode + '_Секторы';
        break;
      case 'sector':
      case 'employees':
        _exportData = _unitExportData(data.employees, 'name');
        cols = _unitExportCols('Сотрудник');
        pageName = mode + '_Сотрудники';
        break;
      case 'employee':
        _exportData = _taskExportData(data.tasks);
        cols = _taskExportColsSimple();
        pageName = mode + '_Задачи';
        break;
      default:
        _exportData = [];
        return;
    }

    if (_exportData.length) {
      _buildExport('anExportTop', pageName, cols, _exportMeta(data));
    }
  }

  function _buildExport(containerId, pageName, columns, meta) {
    // Всегда рендерим в верхнюю панель
    var targetId = 'anExportTop';
    var container = document.getElementById(targetId);
    if (!container || typeof buildExportDropdown !== 'function') return;
    container.innerHTML = '';
    buildExportDropdown(targetId, {
      pageName: pageName,
      columns: columns,
      meta: meta || [],
      getAllData: function () {
        return _exportData;
      },
      getFilteredData: function () {
        return _exportData;
      },
    });
  }

  /* ── Снимок месяца ────────────────────────────────────────────────────
   * Переиспользует ту же разметку и тот же API, что и СП.
   * Показывается только при строго одном годе и одном месяце.
   * ────────────────────────────────────────────────────────────────── */
  function loadMonthSnapshot() {
    var el = document.getElementById('monthSnapshot');
    if (!el) return;

    var years = idsToList(currentYears);
    var months = idsToList(currentMonths);

    // Требуется ровно один год + один месяц — иначе снимок не имеет смысла
    if (years.length !== 1 || months.length !== 1) {
      el.style.display = 'none';
      return;
    }

    var y = parseInt(years[0]);
    var m = parseInt(months[0]);
    if (!y || !m) {
      el.style.display = 'none';
      return;
    }

    el.style.display = '';
    var monthKey = y + '-' + (m < 10 ? '0' + m : '' + m);
    var url = '/api/analytics/month_snapshot/?month=' + monthKey;

    // Пробрасываем фильтры, поддерживаемые API (единичные).
    // При множественных значениях снимок считается по объединению (без фильтра) —
    // чтобы не скрывать данные.
    var dcs = idsToList(currentDeptCodes);
    if (dcs.length === 1) url += '&dept=' + encodeURIComponent(dcs[0]);
    var sids = idsToList(currentSectorIds);
    if (sids.length === 1) url += '&sector_id=' + sids[0];
    var cids = idsToList(currentCenterIds);
    if (cids.length === 1) url += '&center_id=' + cids[0];
    var pids = idsToList(currentProjectIds);
    if (pids.length === 1) url += '&project_id=' + pids[0];

    fetch(url)
      .then(function (r) {
        return r.ok ? r.json() : null;
      })
      .then(function (data) {
        if (data) renderMonthSnapshot(data);
      })
      .catch(function (e) {
        console.error('month_snapshot error:', e);
      });
  }

  function renderMonthSnapshot(data) {
    function setText(id, v) {
      var e = document.getElementById(id);
      if (e) e.textContent = v;
    }
    function setBar(id, pct) {
      var e = document.getElementById(id);
      if (e) e.style.width = Math.max(0, Math.min(100, pct)) + '%';
    }

    var MONTHS = [
      'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
    ];
    var parts = (data.month || '').split('-');
    var year = parseInt(parts[0]);
    var mon = parseInt(parts[1]);
    setText('snapMonthLabel', isNaN(mon) ? '—' : MONTHS[mon - 1] + ' ' + year);

    var mt = data.month_tasks || {};
    var d = data.debts || {};

    setText('snapMonthTotal', mt.total || 0);
    setText('snapDone', mt.done || 0);
    setText('snapEarly', mt.done_early || 0);
    setText('snapOverdue', mt.overdue || 0);
    setText('snapInwork', mt.inwork || 0);

    setBar('snapDoneBar', mt.done_pct || 0);
    setBar('snapEarlyBar', mt.done_early_pct || 0);
    setBar('snapOverdueBar', mt.overdue_pct || 0);
    setBar('snapInworkBar', mt.inwork_pct || 0);

    setText('snapDebtTotal', d.total || 0);
    setText('snapDebtClosed', d.closed || 0);
    setText('snapDebtHanging', d.hanging || 0);
    setBar('snapDebtClosedBar', d.closed_pct || 0);
    setBar('snapDebtHangingBar', d.hanging_pct || 0);

    var closed = mt.closed || 0;
    var total = mt.total || 0;
    setText('snapInlineMonth', total ? closed + '/' + total : '0');
    setText('snapInlineDebt', d.total ? d.closed + '/' + d.total : '0');
  }

  // Разворачивание/сворачивание блока снимка
  window.anToggleSnapshot = function () {
    var el = document.getElementById('monthSnapshot');
    if (!el) return;
    el.classList.toggle('is-open');
    try {
      localStorage.setItem(
        'an_snapshot_open',
        el.classList.contains('is-open') ? '1' : '0',
      );
    } catch (e) {
      /* ignore quota */
    }
  };

  // Восстановление состояния снимка
  (function restoreSnapshotState() {
    var el = document.getElementById('monthSnapshot');
    if (!el) return;
    var saved = localStorage.getItem('an_snapshot_open');
    if (saved === '0') {
      el.classList.remove('is-open');
    } else {
      el.classList.add('is-open');
    }
  })();

  /* ── Init ─────────────────────────────────────────────────────────────── */
  loadData();
})();
