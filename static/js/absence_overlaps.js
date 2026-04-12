/* ══════════════════════════════════════════════════════════════════════
   absence_overlaps.js — Модалка проверки пересечений отсутствий
   Используется в Плане отпусков и Командировках
   ══════════════════════════════════════════════════════════════════════ */

/**
 * Открывает модалку пересечений.
 * @param {Object} cfg
 *   - context: 'vacations' | 'trips'
 *   - employees: [{id, value, dept}]  — список сотрудников
 *   - getCsrfToken: () => string
 */
function openOverlapsModal(cfg) {
  var ctx = cfg.context || 'vacations';
  var employees = cfg.employees || [];
  var getCsrf = cfg.getCsrfToken;

  // Группируем сотрудников по отделам
  var deptGroups = {};
  employees.forEach(function (emp) {
    var d = emp.dept || 'Без отдела';
    if (!deptGroups[d]) deptGroups[d] = [];
    deptGroups[d].push(emp);
  });
  var sortedDepts = Object.keys(deptGroups).sort(function (a, b) {
    return a.localeCompare(b, 'ru');
  });

  var now = new Date();
  var yearStart = now.getFullYear() + '-01-01';
  var yearEnd = now.getFullYear() + '-12-31';

  var crossLabel = ctx === 'vacations' ? 'Учитывать командировки' : 'Учитывать отпуска';

  var html =
    '<div class="overlap-modal-content">' +
    '<div class="overlap-form">' +
    '<div class="overlap-form-row">' +
    '<label class="overlap-label">Сотрудники:</label>' +
    '<div class="overlap-emp-select-wrap">' +
    '<input type="text" class="overlap-emp-search" id="ovEmpSearch" placeholder="Поиск по ФИО..." oninput="filterOverlapEmps()">' +
    '<div class="overlap-emp-actions">' +
    '<button class="btn btn-xs btn-outline" onclick="ovSelectAll()">Выбрать всех</button>' +
    '<button class="btn btn-xs btn-outline" onclick="ovDeselectAll()">Снять все</button>' +
    '<span class="overlap-selected-count" id="ovSelectedCount">Выбрано: 0</span>' +
    '</div>' +
    '<div class="overlap-emp-list" id="ovEmpList">';

  sortedDepts.forEach(function (dept) {
    html +=
      '<div class="overlap-emp-group" data-dept="' +
      escapeHtml(dept) +
      '">' +
      '<label class="overlap-dept-header"><input type="checkbox" class="ov-dept-cb" data-dept="' +
      escapeHtml(dept) +
      '" onchange="ovToggleDept(this)"> <strong>' +
      escapeHtml(dept) +
      '</strong> <span class="text-muted">(' +
      deptGroups[dept].length +
      ')</span></label>';
    deptGroups[dept].forEach(function (emp) {
      html +=
        '<label class="overlap-emp-item"><input type="checkbox" class="ov-emp-cb" value="' +
        emp.id +
        '" data-dept="' +
        escapeHtml(dept) +
        '" onchange="ovUpdateCount()"> ' +
        escapeHtml(emp.value) +
        '</label>';
    });
    html += '</div>';
  });

  html +=
    '</div></div></div>' +
    '<div class="overlap-form-row">' +
    '<label class="overlap-label">Период:</label>' +
    '<div style="display:flex;gap:8px;align-items:center;">' +
    '<input type="date" id="ovDateFrom" value="' +
    yearStart +
    '" class="form-input" style="width:150px;">' +
    '<span>—</span>' +
    '<input type="date" id="ovDateTo" value="' +
    yearEnd +
    '" class="form-input" style="width:150px;">' +
    '</div></div>' +
    '<div class="overlap-form-row">' +
    '<label class="overlap-check-label"><input type="checkbox" id="ovCrossCheck" checked> ' +
    crossLabel +
    '</label>' +
    '</div>' +
    '<div style="text-align:right;margin-top:12px;">' +
    '<button class="btn btn-primary" onclick="runOverlapCheck(\'' +
    ctx +
    '\')"><i class="fas fa-search"></i> Проверить</button>' +
    '</div></div>' +
    '<div id="ovResults" style="display:none;"></div>';

  // Сохраняем getCsrf глобально для runOverlapCheck
  window._ovGetCsrf = getCsrf;

  openModal({ title: 'Проверка пересечений отсутствий', body: html, width: '900px' });
}

function filterOverlapEmps() {
  var q = (document.getElementById('ovEmpSearch')?.value || '').toLowerCase();
  document.querySelectorAll('#ovEmpList .overlap-emp-item').forEach(function (el) {
    var name = el.textContent.toLowerCase();
    el.style.display = name.indexOf(q) >= 0 ? '' : 'none';
  });
  // Скрываем пустые группы
  document.querySelectorAll('#ovEmpList .overlap-emp-group').forEach(function (g) {
    var visible = g.querySelectorAll('.overlap-emp-item[style=""], .overlap-emp-item:not([style])');
    g.style.display = visible.length > 0 ? '' : 'none';
  });
}

function ovSelectAll() {
  document.querySelectorAll('#ovEmpList .ov-emp-cb').forEach(function (cb) {
    if (cb.closest('.overlap-emp-item').style.display !== 'none') cb.checked = true;
  });
  document.querySelectorAll('#ovEmpList .ov-dept-cb').forEach(function (cb) {
    cb.checked = true;
  });
  ovUpdateCount();
}

function ovDeselectAll() {
  document.querySelectorAll('#ovEmpList .ov-emp-cb').forEach(function (cb) {
    cb.checked = false;
  });
  document.querySelectorAll('#ovEmpList .ov-dept-cb').forEach(function (cb) {
    cb.checked = false;
  });
  ovUpdateCount();
}

function ovToggleDept(deptCb) {
  var dept = deptCb.dataset.dept;
  var checked = deptCb.checked;
  document
    .querySelectorAll('#ovEmpList .ov-emp-cb[data-dept="' + dept + '"]')
    .forEach(function (cb) {
      cb.checked = checked;
    });
  ovUpdateCount();
}

function ovUpdateCount() {
  var count = document.querySelectorAll('#ovEmpList .ov-emp-cb:checked').length;
  var el = document.getElementById('ovSelectedCount');
  if (el) el.textContent = 'Выбрано: ' + count;
}

function runOverlapCheck(ctx) {
  var ids = [];
  document.querySelectorAll('#ovEmpList .ov-emp-cb:checked').forEach(function (cb) {
    ids.push(parseInt(cb.value));
  });
  if (ids.length < 2) {
    showToast('Выберите минимум 2 сотрудников', 'warning');
    return;
  }

  var dateFrom = document.getElementById('ovDateFrom')?.value || '';
  var dateTo = document.getElementById('ovDateTo')?.value || '';
  var crossCheck = document.getElementById('ovCrossCheck')?.checked || false;

  var body = {
    employee_ids: ids,
    date_from: dateFrom || null,
    date_to: dateTo || null,
    include_vacations: ctx === 'vacations' ? true : crossCheck,
    include_trips: ctx === 'trips' ? true : crossCheck,
  };

  var btn = document.querySelector('.overlap-modal-content .btn-primary');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Проверяю...';
  }

  fetch('/api/absence_overlaps/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': window._ovGetCsrf(),
    },
    body: JSON.stringify(body),
  })
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      if (data.error) {
        showToast(data.error, 'error');
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fas fa-search"></i> Проверить';
        }
        return;
      }
      renderOverlapResults(data, dateFrom, dateTo);
    })
    .catch(function (err) {
      showToast('Ошибка запроса: ' + err, 'error');
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Проверить';
      }
    });
}

function renderOverlapResults(data, dateFrom, dateTo) {
  var el = document.getElementById('ovResults');
  if (!el) return;
  el.style.display = '';

  var s = data.summary;
  var html = '';

  // Сводка
  html += '<div class="overlap-summary">';
  if (s.total_overlaps === 0) {
    html +=
      '<div class="overlap-no-result"><i class="fas fa-check-circle" style="color:var(--success);font-size:24px;"></i><br>Пересечений не найдено</div>';
    el.innerHTML = html + '</div>';
    return;
  }
  html +=
    '<div class="overlap-summary-stats">' +
    '<span class="overlap-stat"><i class="fas fa-exclamation-triangle" style="color:var(--danger);"></i> Пересечений: <strong>' +
    s.total_overlaps +
    '</strong></span>' +
    '<span class="overlap-stat"><i class="fas fa-users"></i> Сотрудников затронуто: <strong>' +
    s.employees_involved +
    '</strong></span>' +
    '<span class="overlap-stat"><i class="fas fa-calendar-day"></i> Макс. дней пересечения: <strong>' +
    s.max_overlap_days +
    '</strong></span>' +
    '</div></div>';

  // Таблица пересечений
  html +=
    '<div class="overlap-table-wrap"><table class="overlap-table">' +
    '<thead><tr><th>Период пересечения</th><th>Дней</th><th>Сотрудники</th></tr></thead><tbody>';
  data.overlaps.forEach(function (ov) {
    html +=
      '<tr><td class="ov-dates">' +
      formatDate(ov.overlap_start) +
      ' — ' +
      formatDate(ov.overlap_end) +
      '</td>' +
      '<td class="ov-days">' +
      ov.duration_days +
      '</td><td>';
    ov.employees.forEach(function (emp) {
      var badge = emp.type === 'vacation' ? 'ov-badge-vac' : 'ov-badge-trip';
      var typeLabel = emp.type === 'vacation' ? 'Отпуск' : 'Командировка';
      html +=
        '<div class="ov-emp-row"><span class="ov-emp-name">' +
        escapeHtml(emp.employee_name) +
        '</span> ' +
        '<span class="ov-badge ' +
        badge +
        '">' +
        typeLabel +
        '</span> ' +
        '<span class="ov-emp-detail">' +
        escapeHtml(emp.detail) +
        ' (' +
        formatDate(emp.period_start) +
        ' — ' +
        formatDate(emp.period_end) +
        ')</span></div>';
    });
    html += '</td></tr>';
  });
  html += '</tbody></table></div>';

  // Мини-таймлайн
  if (data.timeline && data.timeline.length > 0) {
    html += _buildTimeline(data.timeline, data.overlaps, dateFrom, dateTo);
  }

  el.innerHTML = html;
}

function _buildTimeline(timeline, overlaps, dateFrom, dateTo) {
  // Определяем диапазон дат
  var minD = dateFrom ? new Date(dateFrom) : null;
  var maxD = dateTo ? new Date(dateTo) : null;
  timeline.forEach(function (row) {
    row.periods.forEach(function (p) {
      var s = new Date(p.start),
        e = new Date(p.end);
      if (!minD || s < minD) minD = s;
      if (!maxD || e > maxD) maxD = e;
    });
  });
  if (!minD || !maxD) return '';
  var totalMs = maxD - minD;
  if (totalMs <= 0) return '';

  var html =
    '<div class="overlap-timeline"><h4 style="margin:16px 0 8px;">Таймлайн отсутствий</h4>';

  // Месячные метки
  html += '<div class="ov-tl-header">';
  var cur = new Date(minD.getFullYear(), minD.getMonth(), 1);
  var monthNames = [
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
  while (cur <= maxD) {
    var mStart = Math.max(0, cur - minD);
    var left = (mStart / totalMs) * 100;
    html +=
      '<span class="ov-tl-month" style="left:' +
      left.toFixed(1) +
      '%">' +
      monthNames[cur.getMonth()] +
      '</span>';
    cur.setMonth(cur.getMonth() + 1);
  }
  html += '</div>';

  timeline.forEach(function (row) {
    html +=
      '<div class="ov-tl-row">' +
      '<div class="ov-tl-name" title="' +
      escapeHtml(row.employee_name) +
      '">' +
      escapeHtml(row.employee_name) +
      ' <span class="text-muted">(' +
      escapeHtml(row.dept) +
      ')</span></div>' +
      '<div class="ov-tl-bars">';
    row.periods.forEach(function (p) {
      var s = new Date(p.start),
        e = new Date(p.end);
      var left = ((s - minD) / totalMs) * 100;
      var width = ((e - s) / totalMs) * 100;
      if (width < 0.5) width = 0.5;
      var cls = p.type === 'vacation' ? 'ov-bar-vac' : 'ov-bar-trip';
      var tip =
        (p.type === 'vacation' ? 'Отпуск: ' : 'Командировка: ') +
        p.detail +
        ' (' +
        formatDate(p.start) +
        ' — ' +
        formatDate(p.end) +
        ')';
      html +=
        '<div class="ov-tl-bar ' +
        cls +
        '" style="left:' +
        left.toFixed(2) +
        '%;width:' +
        width.toFixed(2) +
        '%;" title="' +
        escapeHtml(tip) +
        '"></div>';
    });
    html += '</div></div>';
  });

  // Зоны пересечения
  // (показываем полупрозрачные полосы поверх таймлайна)

  html += '</div>';
  return html;
}

function formatDate(d) {
  if (!d) return '';
  var parts = d.split('-');
  if (parts.length === 3) return parts[2] + '.' + parts[1] + '.' + parts[0];
  return d;
}
