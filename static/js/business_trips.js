/* ── План командировок — SPA логика ─────────────────────────────────────────── */
'use strict';

/* ── Конфигурация (из Django template) ─────────────────────────────────────── */
var _cfgEl = document.getElementById('bt-config');
var _cfg = _cfgEl ? JSON.parse(_cfgEl.textContent) : {};
var IS_WRITER = _cfg.is_writer || false;
var CURRENT_YEAR = _cfg.current_year || new Date().getFullYear();

/* ── Константы ─────────────────────────────────────────────────────────────── */
var MONTHS = ['','Январь','Февраль','Март','Апрель','Май','Июнь',
              'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
var MONTHS_SHORT = ['','Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'];
var WEEKDAYS = ['пн','вт','ср','чт','пт','сб','вс'];

var STATUS_COLORS = {
  plan:   { bg: '#ede9fe', color: '#6d28d9', bar: 'linear-gradient(135deg,#8b5cf6,#a78bfa)' },
  active: { bg: '#dbeafe', color: '#1d4ed8', bar: 'linear-gradient(135deg,#2563eb,#60a5fa)' },
  done:   { bg: '#e2e8f0', color: '#475569', bar: 'linear-gradient(135deg,#64748b,#94a3b8)' },
  cancel: { bg: '#fee2e2', color: '#b91c1c', bar: 'linear-gradient(135deg,#ef4444,#f87171)' },
};
var STATUS_LABELS = { plan: 'Запланирована', active: 'В процессе', done: 'Завершена', cancel: 'Отменена' };

/* ── Состояние ─────────────────────────────────────────────────────────────── */
var trips = [];
var holidays = {};
var curYear = CURRENT_YEAR;
var curMonth = new Date().getMonth() + 1;
var curView = 'gantt'; // 'gantt' | 'matrix'
var editingId = null;
var deptFilter = '';
var statusFilter = '';
var searchFilter = '';

/* ── Хелперы ───────────────────────────────────────────────────────────────── */
function pad2(n) { return String(n).padStart(2, '0'); }
function daysInMonth(y, m) { return new Date(y, m, 0).getDate(); }
function isWeekend(y, m, d) {
  var dow = new Date(y, m - 1, d).getDay();
  return dow === 0 || dow === 6;
}
function isHoliday(y, m, d) {
  return !!holidays[y + '-' + pad2(m) + '-' + pad2(d)];
}
function isNonWorking(y, m, d) {
  return isHoliday(y, m, d) || isWeekend(y, m, d);
}

/* ── Загрузка данных ───────────────────────────────────────────────────────── */
async function loadTrips() {
  try {
    var url = '/api/business_trips/?year=' + curYear;
    if (deptFilter) url += '&dept=' + encodeURIComponent(deptFilter);
    if (statusFilter) url += '&status=' + encodeURIComponent(statusFilter);
    if (searchFilter) url += '&executor=' + encodeURIComponent(searchFilter);
    var resp = await fetch(url);
    trips = await resp.json();
  } catch (e) {
    trips = [];
    showToast('Ошибка загрузки командировок', 'error');
  }
  render();
}

async function loadHolidays() {
  try {
    var resp = await fetch('/api/holidays/?year=' + curYear);
    var data = await resp.json();
    holidays = {};
    (data || []).forEach(function(h) { holidays[h.date] = h.name; });
  } catch (e) {
    holidays = {};
  }
}

/* ── Рендеринг ─────────────────────────────────────────────────────────────── */
function render() {
  updateStats();
  if (curView === 'gantt') {
    renderGantt();
    document.getElementById('ganttView').style.display = '';
    document.getElementById('matrixView').style.display = 'none';
    document.getElementById('monthBar').style.display = '';
  } else {
    renderMatrix();
    document.getElementById('ganttView').style.display = 'none';
    document.getElementById('matrixView').style.display = '';
    document.getElementById('monthBar').style.display = 'none';
  }
}

function updateStats() {
  var active = trips.filter(function(t) { return t.status !== 'cancel'; });
  var totalDays = active.reduce(function(s, t) { return s + (t.duration_days || 0); }, 0);
  var el = document.getElementById('tripStats');
  if (el) el.textContent = active.length + ' командир. · ' + totalDays + ' чел.-дн.';
}

/* ── Gantt ──────────────────────────────────────────────────────────────────── */
function renderGantt() {
  var container = document.getElementById('ganttView');
  var dim = daysInMonth(curYear, curMonth);

  // Собираем сотрудников, у которых есть командировки в этом месяце
  var monthStart = new Date(curYear, curMonth - 1, 1);
  var monthEnd = new Date(curYear, curMonth - 1, dim);
  var empTrips = {}; // executor -> [trip, ...]
  var empOrder = [];

  trips.forEach(function(t) {
    if (t.status === 'cancel') return; // скрываем отменённые в Gantt
    var ts = new Date(t.date_start);
    var te = new Date(t.date_end);
    if (te < monthStart || ts > monthEnd) return;
    var key = t.executor || ('emp_' + t.employee_id);
    if (!empTrips[key]) { empTrips[key] = []; empOrder.push(key); }
    empTrips[key].push(t);
  });

  if (empOrder.length === 0) {
    container.innerHTML = '<div class="bt-empty"><i class="fas fa-plane-slash"></i><p>Нет командировок в ' + MONTHS[curMonth] + ' ' + curYear + '</p></div>';
    return;
  }

  var cols = dim + 1; // name + days
  var html = '<div class="gantt-wrap"><div class="gantt-grid" style="grid-template-columns:180px repeat(' + dim + ',1fr)">';

  // Header row
  html += '<div class="g-hdr" style="text-align:left;padding-left:12px">Сотрудник</div>';
  for (var d = 1; d <= dim; d++) {
    var nw = isNonWorking(curYear, curMonth, d);
    html += '<div class="g-hdr' + (nw ? ' g-we' : '') + '">' + d + '</div>';
  }

  // Employee rows
  empOrder.forEach(function(key) {
    var rowTrips = empTrips[key];
    var first = rowTrips[0];
    html += '<div class="g-name"><span class="g-name-text">' + (first.executor || '?') + '</span><span class="g-dept">' + (first.dept || '') + '</span></div>';
    for (var d = 1; d <= dim; d++) {
      var nw = isNonWorking(curYear, curMonth, d);
      html += '<div class="g-cell' + (nw ? ' g-we' : '') + '"';

      // Check if any trip starts on this day
      rowTrips.forEach(function(t) {
        var ts = new Date(t.date_start);
        var te = new Date(t.date_end);
        var startDay = ts < monthStart ? 1 : ts.getDate();
        var endDay = te > monthEnd ? dim : te.getDate();
        if (d === startDay) {
          var span = endDay - startDay + 1;
          var sc = STATUS_COLORS[t.status] || STATUS_COLORS.plan;
          html += ' style="position:relative">';
          html += '<div class="g-bar" style="width:calc(' + (span * 100) + '% + ' + (span - 1) + 'px);background:' + sc.bar + '" title="' + t.location + ' · ' + t.date_start + ' — ' + t.date_end + '"';
          if (IS_WRITER) html += ' onclick="openEditTripModal(' + t.id + ')"';
          html += '>' + (span >= 3 ? t.location.substring(0, 15) : '') + '</div>';
          return;
        }
      });

      if (!html.endsWith('>')) html += '>';
      html += '</div>';
    }
  });

  html += '</div></div>';
  container.innerHTML = html;
}

/* ── Матрица ───────────────────────────────────────────────────────────────── */
function renderMatrix() {
  var container = document.getElementById('matrixView');

  // Группируем по сотрудникам
  var empMap = {}; // executor -> {trips, dept, employee_id}
  var empOrder = [];
  trips.forEach(function(t) {
    var key = t.executor || ('emp_' + t.employee_id);
    if (!empMap[key]) {
      empMap[key] = { trips: [], dept: t.dept, employee_id: t.employee_id, name: t.executor };
      empOrder.push(key);
    }
    empMap[key].trips.push(t);
  });

  if (empOrder.length === 0) {
    container.innerHTML = '<div class="bt-empty"><i class="fas fa-plane-slash"></i><p>Нет командировок в ' + curYear + '</p></div>';
    return;
  }

  var html = '<div class="matrix-wrap"><table class="matrix-table">';
  html += '<thead><tr><th class="th-emp">Сотрудник</th>';
  for (var m = 1; m <= 12; m++) html += '<th>' + MONTHS_SHORT[m] + '</th>';
  html += '<th>Итого</th></tr></thead><tbody>';

  var monthTotals = new Array(13).fill(0); // [0..12], 0=unused

  empOrder.forEach(function(key) {
    var emp = empMap[key];
    var initials = (emp.name || '??').split(' ').map(function(w) { return w[0] || ''; }).join('').substring(0, 2).toUpperCase();
    html += '<tr><td class="td-emp"><div class="emp-cell"><div class="emp-ava">' + initials + '</div><div><div class="emp-name">' + (emp.name || '?') + '</div><div class="emp-dept">' + (emp.dept || '') + '</div></div></div></td>';

    var yearTotal = 0;

    for (var m = 1; m <= 12; m++) {
      var monthTrips = emp.trips.filter(function(t) {
        var ts = new Date(t.date_start);
        var te = new Date(t.date_end);
        return ts.getMonth() + 1 <= m && te.getMonth() + 1 >= m && ts.getFullYear() <= curYear && te.getFullYear() >= curYear;
      });

      if (monthTrips.length === 0) {
        html += '<td></td>';
      } else {
        html += '<td>';
        monthTrips.forEach(function(t) {
          // Считаем дни в этом месяце
          var mStart = new Date(curYear, m - 1, 1);
          var mEnd = new Date(curYear, m, 0);
          var ts = new Date(t.date_start);
          var te = new Date(t.date_end);
          var effStart = ts > mStart ? ts : mStart;
          var effEnd = te < mEnd ? te : mEnd;
          var days = Math.round((effEnd - effStart) / 86400000) + 1;
          if (days < 1) days = 1;

          var sc = STATUS_COLORS[t.status] || STATUS_COLORS.plan;
          var cls = 'trip-chip chip-' + t.status;
          html += '<span class="' + cls + '" title="' + t.location + ' · ' + STATUS_LABELS[t.status] + '"';
          if (IS_WRITER) html += ' onclick="openEditTripModal(' + t.id + ')"';
          html += '>' + days + 'д</span> ';

          if (t.status !== 'cancel') {
            yearTotal += days;
            monthTotals[m] += days;
          }
        });
        html += '</td>';
      }
    }

    html += '<td class="td-total">' + (yearTotal || '') + '</td></tr>';
  });

  // Итого
  var grandTotal = monthTotals.reduce(function(s, v) { return s + v; }, 0);
  html += '<tr class="row-total"><td>Итого (чел.-дн.)</td>';
  for (var m = 1; m <= 12; m++) html += '<td>' + (monthTotals[m] || '') + '</td>';
  html += '<td class="td-total">' + grandTotal + '</td></tr>';

  html += '</tbody></table></div>';
  container.innerHTML = html;
}

/* ── Переключение вида ─────────────────────────────────────────────────────── */
function switchView(view) {
  curView = view;
  document.querySelectorAll('.view-tab').forEach(function(el) {
    el.classList.toggle('active', el.dataset.view === view);
  });
  render();
}

/* ── Месяц-кнопки ──────────────────────────────────────────────────────────── */
function buildMonthBar() {
  var bar = document.getElementById('monthBar');
  if (!bar) return;
  var html = '';
  for (var m = 1; m <= 12; m++) {
    html += '<button class="month-btn' + (m === curMonth ? ' active' : '') + '" data-month="' + m + '" onclick="selectMonth(' + m + ')">' + MONTHS_SHORT[m] + '</button>';
  }
  bar.innerHTML = html;
}

function selectMonth(m) {
  curMonth = m;
  document.querySelectorAll('.month-btn').forEach(function(el) {
    el.classList.toggle('active', parseInt(el.dataset.month) === m);
  });
  render();
}

/* ── Год ───────────────────────────────────────────────────────────────────── */
function changeYear() {
  curYear = parseInt(document.getElementById('yearSel').value);
  loadHolidays().then(loadTrips);
}

/* ── Фильтры ───────────────────────────────────────────────────────────────── */
function applyDeptFilter() {
  deptFilter = document.getElementById('deptFilter').value;
  loadTrips();
}
function applyStatusFilter() {
  statusFilter = document.getElementById('statusFilter').value;
  loadTrips();
}
var _searchTimeout;
function applySearch() {
  clearTimeout(_searchTimeout);
  _searchTimeout = setTimeout(function() {
    searchFilter = document.getElementById('searchInput').value.trim();
    loadTrips();
  }, 300);
}

/* ── CRUD Модалка ──────────────────────────────────────────────────────────── */
function openAddTripModal() {
  editingId = null;
  document.getElementById('tripModalTitle').textContent = 'Новая командировка';
  document.getElementById('tripForm').reset();
  document.getElementById('fieldDateStart').value = '';
  document.getElementById('fieldDateEnd').value = '';
  document.getElementById('fieldStatus').value = 'plan';
  document.getElementById('tripDeleteBtn').style.display = 'none';
  document.getElementById('tripModalError').style.display = 'none';
  document.getElementById('tripModal').classList.add('open');
}

function openEditTripModal(id) {
  var t = trips.find(function(x) { return x.id === id; });
  if (!t) return;
  editingId = id;
  document.getElementById('tripModalTitle').textContent = 'Редактировать командировку';
  document.getElementById('fieldEmployee').value = t.executor || '';
  document.getElementById('fieldLocation').value = t.location || '';
  document.getElementById('fieldPurpose').value = t.purpose || '';
  document.getElementById('fieldDateStart').value = t.date_start || '';
  document.getElementById('fieldDateEnd').value = t.date_end || '';
  document.getElementById('fieldStatus').value = t.status || 'plan';
  document.getElementById('fieldNotes').value = t.notes || '';
  document.getElementById('tripDeleteBtn').style.display = '';
  document.getElementById('tripModalError').style.display = 'none';
  document.getElementById('tripModal').classList.add('open');
}

function closeTripModal() {
  document.getElementById('tripModal').classList.remove('open');
  editingId = null;
}

async function saveTrip() {
  var errEl = document.getElementById('tripModalError');
  var executor = document.getElementById('fieldEmployee').value.trim();
  var location = document.getElementById('fieldLocation').value.trim();
  var purpose = document.getElementById('fieldPurpose').value.trim();
  var dateStart = document.getElementById('fieldDateStart').value;
  var dateEnd = document.getElementById('fieldDateEnd').value;
  var status = document.getElementById('fieldStatus').value;
  var notes = document.getElementById('fieldNotes').value.trim();

  if (!executor || !location || !dateStart || !dateEnd) {
    errEl.textContent = 'Заполните обязательные поля';
    errEl.style.display = 'block';
    return;
  }

  var body = { executor: executor, location: location, purpose: purpose,
               date_start: dateStart, date_end: dateEnd, status: status, notes: notes };

  var btn = document.getElementById('tripSaveBtn');
  btn.disabled = true;

  try {
    var url, method;
    if (editingId) {
      url = '/api/business_trips/' + editingId + '/';
      method = 'PUT';
    } else {
      url = '/api/business_trips/';
      method = 'POST';
    }
    var resp = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(body),
    });
    var data = await resp.json();
    if (!resp.ok) {
      errEl.textContent = data.error || 'Ошибка сохранения';
      errEl.style.display = 'block';
      return;
    }
    closeTripModal();
    showToast(editingId ? 'Командировка обновлена' : 'Командировка создана', 'success');
    await loadTrips();
  } catch (e) {
    errEl.textContent = 'Сетевая ошибка';
    errEl.style.display = 'block';
  } finally {
    btn.disabled = false;
  }
}

async function deleteTrip() {
  if (!editingId) return;
  if (!confirm('Удалить командировку?')) return;

  try {
    var resp = await fetch('/api/business_trips/' + editingId + '/', {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    if (resp.ok) {
      closeTripModal();
      showToast('Командировка удалена', 'success');
      await loadTrips();
    } else {
      showToast('Ошибка удаления', 'error');
    }
  } catch (e) {
    showToast('Сетевая ошибка', 'error');
  }
}

/* ── Инициализация ─────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  buildMonthBar();
  loadHolidays().then(loadTrips);
  // Экспорт
  if (typeof buildExportDropdown === 'function') {
    buildExportDropdown('exportBtnContainer', {
      pageName: 'Командировки',
      columns: [
        { key: 'executor',    header: 'Сотрудник',     width: 160 },
        { key: 'dept',        header: 'Отдел',         width: 60  },
        { key: 'location',    header: 'Место',         width: 200 },
        { key: 'purpose',     header: 'Цель',          width: 200 },
        { key: 'date_start',  header: 'Дата начала',   width: 100 },
        { key: 'date_end',    header: 'Дата окончания', width: 100 },
        { key: 'duration_days', header: 'Дней',        width: 60  },
        { key: 'status_display', header: 'Статус',     width: 100 },
        { key: 'notes',       header: 'Примечания',    width: 200 },
      ],
      getAllData: function() { return trips; },
      getFilteredData: function() { return trips; },
    });
  }
});
